"""send_package job — checklist already done; conflict → adapt → judge → prioritize via Mistral."""  # noqa: E501

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import get_mistral_provider
from src.ai.mistral import MistralProvider
from src.channels import service as channels_service
from src.channels.models import Package
from src.graph.models import Claim
from src.jobs import queue as job_queue
from src.jobs.queue import Job
from src.lib.config import settings
from src.pipeline.contracts._common import (
    AdaptationDirection,
    ClaimRef,
    ConflictScope,
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
from src.pipeline.contracts.conflict import (
    CONTRACT_VERSION as CONFLICT_CV,
)
from src.pipeline.contracts.conflict import (
    ConflictInput,
    ConflictOutput,
)
from src.pipeline.contracts.judge import (
    CONTRACT_VERSION as JUDGE_CV,
)
from src.pipeline.contracts.judge import (
    JudgeInput,
    JudgeOutput,
)
from src.pipeline.contracts.prioritization import (
    CONTRACT_VERSION as PRIO_CV,
)
from src.pipeline.contracts.prioritization import (
    PrioritizationInput,
    PrioritizationOutput,
)
from src.pipeline.errors import AgentContractError
from src.pipeline.policies import RenditionAction, RenditionPolicy
from src.pipeline.runner import AgentStage, run_agent
from src.tenancy.models import TeamProfile

logger = logging.getLogger(__name__)

STEP_XCONFLICT = "cross_team_conflict"
STEP_ADAPT = "adaptation"
STEP_JUDGE = "judge"
STEP_PRIO = "prioritization"
STEP_POST = "create_post"


async def _latest_profile(session: AsyncSession, team_id: UUID) -> TeamProfileSnapshot:
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


async def handle_send_package(job: Job, session: AsyncSession) -> None:
    provider: MistralProvider = get_mistral_provider()
    payload = job.payload or {}
    package_id = UUID(str(payload["package_id"]))
    org_id = UUID(str(payload["org_id"]))
    team_id = UUID(str(payload["team_id"]))
    target_team_id = UUID(str(payload["target_team_id"]))

    pkg = await session.get(Package, package_id)
    if pkg is None or pkg.org_id != org_id:
        raise RuntimeError("package not found")

    steps = dict(job.completed_steps or {})
    original = pkg.body
    adapted = original
    what_was_done = "No adaptation"
    fidelity = fit = badge = None
    confidence: float | None = None
    judge_payload: dict = {}
    priority = None
    priority_reason = None

    if STEP_XCONFLICT not in steps:
        sender_claims = (
            await session.execute(
                select(Claim).where(Claim.org_id == org_id, Claim.team_id == team_id)
            )
        ).scalars().all()[:100]
        receiver_claims = (
            await session.execute(
                select(Claim).where(
                    Claim.org_id == org_id, Claim.team_id == target_team_id
                )
            )
        ).scalars().all()[:100]
        claims = list(sender_claims) + list(receiver_claims)
        await channels_service.log_cross_team_access(
            session,
            org_id=org_id,
            team_a=team_id,
            team_b=target_team_id,
            purpose="cross_team_conflict_scan",
            package_id=package_id,
            meta={
                "sender_claims": len(sender_claims),
                "receiver_claims": len(receiver_claims),
            },
        )
        try:
            cout, ctrace = await run_agent(
                AgentStage.conflict,
                ConflictInput(
                    scope=ConflictScope.cross_team,
                    subject_team_id=str(team_id),
                    counterpart_team_id=str(target_team_id),
                    claims=[ClaimRef(claim_id=str(c.id), text=c.text) for c in claims],
                ),
                ConflictOutput,
                provider=provider,
                contract_version=CONFLICT_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
            from src.channels.containment import assert_claim_ids_contained

            allowed = {str(c.id) for c in claims}
            referenced: set[str] = set()
            for item in cout.conflicts:
                referenced.add(str(item.claim_a_id))
                referenced.add(str(item.claim_b_id))
            assert_claim_ids_contained(
                allowed_claim_ids=allowed, referenced_claim_ids=referenced
            )
            attached = [item.model_dump(mode="json") for item in cout.conflicts]
            await job_queue.complete_step(
                session,
                job.id,
                STEP_XCONFLICT,
                {"conflicts": len(attached), "model": ctrace.model},
            )
            # Persist conflicts for post attachment (FR-5.9); send continues (FR-5.10).
            pkg.checklist = {
                **dict(pkg.checklist or {}),
                "cross_team_conflicts": len(attached),
                "attached_conflicts": attached,
            }
            if payload.get("acknowledge_conflicts"):
                pkg.conflicts_acknowledged = True
        except AgentContractError as exc:
            pkg.status = "send_error"
            await session.flush()
            raise RuntimeError(f"cross-team conflict failed: {exc}") from exc
    if STEP_ADAPT not in steps:
        source_profile = await _latest_profile(session, team_id)
        target_profile = await _latest_profile(session, target_team_id)
        try:
            aout, atrace = await run_agent(
                AgentStage.adaptation,
                AdaptationInput(
                    subject_type=SubjectType.post_body,
                    subject_content=original,
                    source_team_profile=source_profile,
                    target_team_profile=target_profile,
                    direction=AdaptationDirection.forward,
                ),
                AdaptationOutput,
                provider=provider,
                contract_version=ADAPT_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
            adapted = aout.body
            what_was_done = aout.what_was_done
            await job_queue.complete_step(
                session,
                job.id,
                STEP_ADAPT,
                {"model": atrace.model, "what_was_done": what_was_done},
            )
        except AgentContractError:
            adapted = original
            what_was_done = "Adaptation failed — shipping original"
            badge = "adaptation_failed"
            await job_queue.complete_step(
                session, job.id, STEP_ADAPT, {"fallback": "original"}
            )

    if STEP_JUDGE not in steps:
        target_profile = await _latest_profile(session, target_team_id)
        fidelity_attempt = 0
        fit_attempt = 0
        action = RenditionAction.ship
        try:
            while True:
                jout, jtrace = await run_agent(
                    AgentStage.judge,
                    JudgeInput(
                        original=original,
                        rendered=adapted,
                        target_profile=target_profile,
                    ),
                    JudgeOutput,
                    provider=provider,
                    contract_version=JUDGE_CV,
                    model=settings.MISTRAL_CHAT_MODEL,
                )
                action = RenditionPolicy.on_verdict(
                    jout, fidelity_attempt=fidelity_attempt, fit_attempt=fit_attempt
                )
                fidelity = (
                    jout.fidelity.verdict.value
                    if hasattr(jout.fidelity.verdict, "value")
                    else str(jout.fidelity.verdict)
                )
                fit = (
                    jout.audience_fit.verdict.value
                    if hasattr(jout.audience_fit.verdict, "value")
                    else str(jout.audience_fit.verdict)
                )
                confidence = jout.overall_confidence
                judge_payload = jout.model_dump(mode="json")
                if action == RenditionAction.retry_fidelity:
                    fidelity_attempt += 1
                    continue
                if action == RenditionAction.retry_fit:
                    fit_attempt += 1
                    # re-adapt once
                    source_profile = await _latest_profile(session, team_id)
                    aout, _ = await run_agent(
                        AgentStage.adaptation,
                        AdaptationInput(
                            subject_type=SubjectType.post_body,
                            subject_content=original,
                            source_team_profile=source_profile,
                            target_team_profile=target_profile,
                            direction=AdaptationDirection.forward,
                        ),
                        AdaptationOutput,
                        provider=provider,
                        contract_version=ADAPT_CV,
                        model=settings.MISTRAL_CHAT_MODEL,
                    )
                    adapted = aout.body
                    what_was_done = aout.what_was_done
                    continue
                break
            if action == RenditionAction.show_original_with_warning:
                adapted = original
                badge = "original_with_warning"
                what_was_done = "Fidelity fail — showing original"
            elif action == RenditionAction.ship_low_confidence:
                badge = "low_confidence"
            await job_queue.complete_step(
                session,
                job.id,
                STEP_JUDGE,
                {"action": action.value, "model": jtrace.model},
            )
        except AgentContractError:
            badge = "low_confidence"
            await job_queue.complete_step(
                session, job.id, STEP_JUDGE, {"fallback": "low_confidence"}
            )

    if STEP_PRIO not in steps:
        try:
            pout, ptrace = await run_agent(
                AgentStage.prioritization,
                PrioritizationInput(
                    content_summary=adapted[:500],
                    signals={"has_bypassed": bool(pkg.bypassed_checks)},
                ),
                PrioritizationOutput,
                provider=provider,
                contract_version=PRIO_CV,
                model=settings.MISTRAL_CHAT_MODEL,
            )
            priority = (
                pout.priority.value if hasattr(pout.priority, "value") else str(pout.priority)  # noqa: E501
            )
            priority_reason = pout.reason
            await job_queue.complete_step(
                session, job.id, STEP_PRIO, {"priority": priority, "model": ptrace.model}  # noqa: E501
            )
        except AgentContractError:
            priority = None
            priority_reason = None
            await job_queue.complete_step(
                session, job.id, STEP_PRIO, {"priority": None}
            )

    if STEP_POST not in steps:
        if pkg.channel_id is None:
            raise RuntimeError("package missing channel")
        from src.graph.models import Node

        topic_tags: list[str] = []
        for raw in pkg.included_node_ids or []:
            try:
                nid = UUID(str(raw))
            except ValueError:
                continue
            node = await session.get(Node, nid)
            if node is not None and node.label:
                topic_tags.append(str(node.label))
        attached = [
            dict(c)
            for c in (pkg.checklist or {}).get("attached_conflicts") or []
            if isinstance(c, dict)
        ]
        await channels_service.create_post_with_rendition(
            session,
            org_id=org_id,
            channel_id=pkg.channel_id,
            package_id=pkg.id,
            original_body=original,
            adapted_body=adapted,
            what_was_done=what_was_done,
            priority=priority,
            priority_reason=priority_reason,
            bypassed_checks=[str(x) for x in (pkg.bypassed_checks or [])],
            fidelity=fidelity,
            fit=fit,
            confidence=confidence,
            badge=badge,
            judge_payload=judge_payload,
            topic_tags=topic_tags,
            attached_conflicts=attached,
        )
        pkg.status = "sent"
        await job_queue.complete_step(session, job.id, STEP_POST, {"ok": True})
        await session.flush()

    logger.info("send_package completed", extra={"package_id": str(package_id)})
