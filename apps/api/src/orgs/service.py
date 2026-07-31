"""Org service — create org + first owner membership."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.channels.models import Package, Post
from src.conflict.models import ReviewItem
from src.graph.models import AgentTraceRow
from src.jobs.queue import JobQueue
from src.review.models import Suggestion
from src.tenancy.models import (
    AdminMetricsResponse,
    MyOrgMembership,
    MyTeamMembership,
    Org,
    OrgMember,
    OrgResponse,
    Team,
    TeamMember,
)


async def create_org(db: AsyncSession, *, user_id: UUID, name: str) -> OrgResponse:
    org = Org(id=uuid.uuid4(), name=name)
    db.add(org)
    db.add(OrgMember(org_id=org.id, user_id=user_id, role="owner"))
    await db.flush()
    return OrgResponse(id=str(org.id), name=org.name, created_at=org.created_at)


async def archive_org(db: AsyncSession, *, org_id: UUID, actor_role: str) -> None:
    if actor_role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the org owner can archive this organization.",
        )
    org = await db.get(Org, org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    org.archived_at = datetime.now(UTC)
    await db.flush()


async def list_my_orgs(db: AsyncSession, *, user_id: UUID) -> list[MyOrgMembership]:
    org_rows = (
        await db.execute(
            select(Org.id, Org.name, OrgMember.role)
            .join(OrgMember, OrgMember.org_id == Org.id)
            .where(OrgMember.user_id == user_id, Org.archived_at.is_(None))
            .order_by(Org.name)
        )
    ).all()

    memberships: list[MyOrgMembership] = []
    for org_id, org_name, org_role in org_rows:
        team_rows = (
            await db.execute(
                select(Team.id, Team.name, TeamMember.role)
                .join(TeamMember, TeamMember.team_id == Team.id)
                .where(
                    Team.org_id == org_id,
                    TeamMember.user_id == user_id,
                    Team.archived_at.is_(None),
                )
                .order_by(Team.name)
            )
        ).all()
        memberships.append(
            MyOrgMembership(
                org_id=str(org_id),
                org_name=org_name,
                role=org_role,
                teams=[
                    MyTeamMembership(
                        team_id=str(team_id), team_name=team_name, role=team_role
                    )
                    for team_id, team_name, team_role in team_rows
                ],
            )
        )
    return memberships


async def get_org_member_role(
    db: AsyncSession, *, org_id: UUID, user_id: UUID
) -> str | None:
    row = await db.scalar(
        select(OrgMember.role).where(
            OrgMember.org_id == org_id, OrgMember.user_id == user_id
        )
    )
    return row


async def get_admin_metrics(
    db: AsyncSession,
    *,
    org_id: UUID,
    actor_role: str,
) -> AdminMetricsResponse:
    if actor_role not in ("owner", "lead"):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization owner role required",
        )

    trace_metrics = (
        await db.execute(
            select(
                func.count(AgentTraceRow.id),
                func.coalesce(func.sum(AgentTraceRow.cost_usd), 0.0),
                func.avg(AgentTraceRow.latency_ms),
            ).where(AgentTraceRow.org_id == org_id)
        )
    ).one()
    job_org_id = JobQueue.payload["org_id"].as_string()
    job_rows = (
        await db.execute(
            select(JobQueue.state, func.count(JobQueue.id))
            .where(job_org_id == str(org_id))
            .group_by(JobQueue.state)
        )
    ).all()
    jobs_by_state = {state: int(count) for state, count in job_rows}
    finished = sum(
        jobs_by_state.get(state, 0) for state in ("completed", "failed", "dead")
    )
    pass_rate = jobs_by_state.get("completed", 0) / finished if finished else None

    async def count_for(model: type[Post] | type[Package] | type[Suggestion]) -> int:
        value = await db.scalar(
            select(func.count(model.id)).where(model.org_id == org_id)
        )
        return int(value or 0)

    resolved_conflicts = int(
        await db.scalar(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.org_id == org_id,
                ReviewItem.status == "resolved",
                ReviewItem.resolved_resolution.is_not(None),
            )
        )
        or 0
    )
    not_a_conflict = int(
        await db.scalar(
            select(func.count(ReviewItem.id)).where(
                ReviewItem.org_id == org_id,
                ReviewItem.resolved_resolution == "not_a_conflict",
            )
        )
        or 0
    )
    fp_rate = (not_a_conflict / resolved_conflicts) if resolved_conflicts else None

    return AdminMetricsResponse(
        trace_count=int(trace_metrics[0] or 0),
        total_cost_usd=float(trace_metrics[1] or 0.0),
        average_latency_ms=float(trace_metrics[2])
        if trace_metrics[2] is not None
        else None,
        job_count=sum(jobs_by_state.values()),
        job_pass_rate=pass_rate,
        post_count=await count_for(Post),
        package_count=await count_for(Package),
        suggestion_count=await count_for(Suggestion),
        conflict_false_positive_rate=fp_rate,
        conflict_resolved_count=resolved_conflicts,
        conflict_not_a_conflict_count=not_a_conflict,
    )
