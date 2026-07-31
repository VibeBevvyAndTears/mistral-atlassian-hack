"""regenerate_rendition job — re-adapt + re-judge a delivered post via Mistral."""

from __future__ import annotations

import logging
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import get_mistral_provider
from src.channels.models import Package, Post, Rendition
from src.jobs import queue as job_queue
from src.jobs.queue import Job
from src.lib.config import settings
from src.pipeline.contracts._common import (
    AdaptationDirection,
    SubjectType,
    TeamProfileSnapshot,
)
from src.pipeline.contracts.adaptation import (
    CONTRACT_VERSION as ADAPT_CV,
)
from src.pipeline.contracts.adaptation import (
    AdaptationInput,
    AdaptationOutput,
)
from src.pipeline.contracts.judge import CONTRACT_VERSION as JUDGE_CV
from src.pipeline.contracts.judge import JudgeInput, JudgeOutput
from src.pipeline.errors import AgentContractError
from src.pipeline.runner import AgentStage, run_agent
from src.tenancy.models import TeamProfile

logger = logging.getLogger(__name__)

STEP_REGEN = "regenerate"


async def _profile(session: AsyncSession, team_id: UUID) -> TeamProfileSnapshot:
    row = (
        await session.execute(
            select(TeamProfile)
            .where(TeamProfile.team_id == team_id)
            .order_by(TeamProfile.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return TeamProfileSnapshot(team_id=str(team_id), version=0, data={})
    return TeamProfileSnapshot(
        team_id=str(team_id), version=row.version, data=dict(row.data or {})
    )


async def handle_regenerate_rendition(job: Job, session: AsyncSession) -> None:
    payload = job.payload or {}
    post_id = UUID(str(payload["post_id"]))
    org_id = UUID(str(payload["org_id"]))
    post = await session.get(Post, post_id)
    if post is None or post.org_id != org_id:
        raise RuntimeError("post not found")
    pkg = await session.get(Package, post.package_id)
    if pkg is None:
        raise RuntimeError("package not found")

    steps = dict(job.completed_steps or {})
    if STEP_REGEN in steps:
        return

    provider = get_mistral_provider()
    adapted = post.original_body
    what = "Regen skipped"
    try:
        aout, _ = await run_agent(
            AgentStage.adaptation,
            AdaptationInput(
                subject_type=SubjectType.post_body,
                subject_content=post.original_body,
                source_team_profile=await _profile(session, pkg.team_id),
                target_team_profile=await _profile(session, pkg.target_team_id),
                direction=AdaptationDirection.forward,
            ),
            AdaptationOutput,
            provider=provider,
            contract_version=ADAPT_CV,
            model=settings.MISTRAL_CHAT_MODEL,
        )
        adapted = aout.body
        what = aout.what_was_done
        jout, _ = await run_agent(
            AgentStage.judge,
            JudgeInput(
                original=post.original_body,
                rendered=adapted,
                target_profile=await _profile(session, pkg.target_team_id),
            ),
            JudgeOutput,
            provider=provider,
            contract_version=JUDGE_CV,
            model=settings.MISTRAL_CHAT_MODEL,
        )
        fid = (
            jout.fidelity.verdict.value
            if hasattr(jout.fidelity.verdict, "value")
            else str(jout.fidelity.verdict)
        )
        fit = (
            jout.audience_fit.verdict.value
            if hasattr(jout.audience_fit.verdict, "value")
            else str(jout.audience_fit.verdict)
        )
        session.add(
            Rendition(
                id=uuid.uuid4(),
                post_id=post.id,
                org_id=org_id,
                body=adapted,
                fidelity_verdict=fid,
                fit_verdict=fit,
                overall_confidence=jout.overall_confidence,
                badge="updated",
                judge_payload=jout.model_dump(mode="json"),
            )
        )
    except (AgentContractError, ValueError, RuntimeError) as exc:
        logger.warning("regen failed: %s", exc)
        what = f"Regen fallback: {exc}"

    post.adapted_body = adapted
    post.what_was_done = what
    post.version = post.version + 1
    post.updated_since_send = True

    # FR-8.1 — notify receiving team when a delivered post changes post-send
    from src.review.service import collapse_notification
    from src.tenancy.models import TeamMember

    receiver_ids = (
        await session.execute(
            select(TeamMember.user_id).where(TeamMember.team_id == pkg.target_team_id)
        )
    ).scalars().all()
    for uid in receiver_ids:
        await collapse_notification(
            session,
            org_id=org_id,
            user_id=uid,
            kind="post_updated",
            post_id=post.id,
            payload={"package_id": str(pkg.id), "version": post.version},
        )

    await job_queue.complete_step(session, job.id, STEP_REGEN, {"ok": True})
    await session.flush()
