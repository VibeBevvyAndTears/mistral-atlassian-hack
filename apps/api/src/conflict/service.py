"""Conflict detection apply + review/decision services (M3)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.conflict.models import (
    Decision,
    DecisionResponse,
    ReviewItem,
    ReviewItemResponse,
)
from src.graph.models import AgentTraceRow, Claim
from src.pipeline.contracts.conflict import ConflictOutput
from src.pipeline.trace import AgentTrace


def _trace_output(trace: AgentTrace) -> dict:
    out = trace.output
    if hasattr(out, "model_dump"):
        return out.model_dump(mode="json", by_alias=True)  # type: ignore[no-any-return]
    return dict(out) if isinstance(out, dict) else {"value": out}


async def apply_conflict(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    document_id: UUID | None,
    out: ConflictOutput,
    trace: AgentTrace,
    job_id: UUID | None = None,
) -> list[ReviewItem]:
    """Persist ConflictOutput as open ReviewItems + AgentTrace (co-txn)."""
    db.add(
        AgentTraceRow(
            id=uuid.uuid4(),
            org_id=org_id,
            team_id=team_id,
            job_id=job_id,
            document_id=document_id,
            stage=trace.stage,
            model=trace.model,
            prompt_version=trace.prompt_version,
            contract_version=trace.contract_version,
            input_hash=trace.input_hash,
            output=_trace_output(trace),
            cost_usd=trace.cost_usd,
            latency_ms=trace.latency_ms,
        )
    )
    created: list[ReviewItem] = []
    for item in out.conflicts:
        class_val = item.class_.value if hasattr(item.class_, "value") else str(item.class_)  # noqa: E501
        sev = item.severity.value if hasattr(item.severity, "value") else str(item.severity)  # noqa: E501
        via = item.matched_via.value if hasattr(item.matched_via, "value") else str(item.matched_via)  # noqa: E501
        row = ReviewItem(
            id=uuid.uuid4(),
            org_id=org_id,
            team_id=team_id,
            claim_a_id=UUID(str(item.claim_a_id)),
            claim_b_id=UUID(str(item.claim_b_id)),
            conflict_class=class_val,
            severity=sev,
            rationale=item.rationale,
            matched_via=via,
            status="open",
        )
        db.add(row)
        created.append(row)
    await db.flush()
    return created


def _to_response(row: ReviewItem) -> ReviewItemResponse:
    return ReviewItemResponse(
        id=str(row.id),
        team_id=str(row.team_id),
        claim_a_id=str(row.claim_a_id),
        claim_b_id=str(row.claim_b_id),
        conflict_class=row.conflict_class,
        severity=row.severity,
        rationale=row.rationale,
        matched_via=row.matched_via,
        status=row.status,
        proposed_resolution=row.proposed_resolution,
        resolved_resolution=row.resolved_resolution,
        created_at=row.created_at,
    )


async def list_review_items(
    db: AsyncSession, *, org_id: UUID, team_id: UUID, status_filter: str | None = None
) -> list[ReviewItemResponse]:
    stmt = select(ReviewItem).where(
        ReviewItem.org_id == org_id, ReviewItem.team_id == team_id
    )
    if status_filter:
        stmt = stmt.where(ReviewItem.status == status_filter)
    stmt = stmt.order_by(ReviewItem.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


async def propose_resolution(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    item_id: UUID,
    user_id: UUID,
    resolution: str,
) -> ReviewItemResponse:
    row = await db.get(ReviewItem, item_id)
    if row is None or row.org_id != org_id or row.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")  # noqa: E501
    if row.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_resolved"
        )
    row.proposed_resolution = resolution
    row.proposed_by = user_id
    row.status = "proposed"
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return _to_response(row)


async def resolve_review_item(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    item_id: UUID,
    user_id: UUID,
    resolution: str,
    actor_role: str,
) -> ReviewItemResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Lead role required"
        )
    row = await db.get(ReviewItem, item_id)
    if row is None or row.org_id != org_id or row.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")  # noqa: E501
    if row.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="already_resolved"
        )
    row.resolved_resolution = resolution
    row.resolved_by = user_id
    row.resolved_at = datetime.now(UTC)
    row.status = "resolved"
    row.updated_at = datetime.now(UTC)
    await db.flush()
    return _to_response(row)


async def promote_decision_claims(
    db: AsyncSession, *, org_id: UUID, team_id: UUID, document_id: UUID | None = None
) -> list[Decision]:
    """Promote claims with claim_type=decision into Decision rows (idempotent)."""
    stmt = select(Claim).where(
        Claim.org_id == org_id,
        Claim.team_id == team_id,
        Claim.claim_type == "decision",
    )
    if document_id is not None:
        stmt = stmt.where(Claim.document_id == document_id)
    claims = (await db.execute(stmt)).scalars().all()
    created: list[Decision] = []
    for claim in claims:
        existing = await db.execute(
            select(Decision).where(Decision.claim_id == claim.id)
        )
        if existing.scalar_one_or_none() is not None:
            continue
        title = claim.text[:512] if claim.text else "Decision"
        decision = Decision(
            id=uuid.uuid4(),
            org_id=org_id,
            team_id=team_id,
            claim_id=claim.id,
            title=title,
            body=claim.text,
            source="claim_promotion",
            owner_team_id=team_id,
            status="open",
        )
        db.add(decision)
        created.append(decision)
    await db.flush()
    return created


def _apply_status_filter(stmt, status_filter: str | None):
    if not status_filter or status_filter == "all":
        return stmt
    if status_filter == "contested":
        return stmt.where(Decision.status == "contested")
    if status_filter == "open":
        # UI "Open" = proposed/open (not agreed/superseded/contested)
        return stmt.where(Decision.status.in_(("open", "proposed")))
    return stmt.where(Decision.status == status_filter)


async def _decision_responses(
    db: AsyncSession, rows: list[Decision]
) -> list[DecisionResponse]:
    from src.tenancy.models import Team

    owner_ids = {d.owner_team_id for d in rows if d.owner_team_id is not None}
    names: dict[UUID, str] = {}
    if owner_ids:
        teams = (
            await db.execute(select(Team).where(Team.id.in_(owner_ids)))
        ).scalars().all()
        names = {t.id: t.name for t in teams}
    return [
        DecisionResponse(
            id=str(d.id),
            team_id=str(d.team_id),
            claim_id=str(d.claim_id),
            title=d.title,
            body=d.body,
            source=d.source,
            status=d.status,
            owner_team_id=str(d.owner_team_id) if d.owner_team_id else None,
            owner_team_name=names.get(d.owner_team_id) if d.owner_team_id else None,
            channel_id=str(d.channel_id) if d.channel_id else None,
            superseded_by=str(d.superseded_by) if d.superseded_by else None,
            created_at=d.created_at,
        )
        for d in rows
    ]


async def list_decisions(
    db: AsyncSession, *, org_id: UUID, team_id: UUID, status_filter: str | None = None
) -> list[DecisionResponse]:
    stmt = select(Decision).where(Decision.org_id == org_id, Decision.team_id == team_id)  # noqa: E501
    stmt = _apply_status_filter(stmt, status_filter)
    rows = list(
        (await db.execute(stmt.order_by(Decision.created_at.desc()))).scalars().all()
    )
    return await _decision_responses(db, rows)


async def list_channel_decisions(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    channel_id: UUID,
    status_filter: str | None = None,
) -> list[DecisionResponse]:
    """FR-6.2 — Decision Register per channel (interaction pair)."""
    from sqlalchemy import or_

    from src.channels.models import Channel

    channel = await db.get(Channel, channel_id)
    if channel is None or channel.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")  # noqa: E501
    if team_id not in (channel.team_a_id, channel.team_b_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")  # noqa: E501

    # Channel-scoped rows + still-unscoped decisions owned by either team in the pair.
    stmt = select(Decision).where(
        Decision.org_id == org_id,
        or_(
            Decision.channel_id == channel_id,
            (
                Decision.channel_id.is_(None)
                & Decision.team_id.in_((channel.team_a_id, channel.team_b_id))
            ),
        ),
    )
    stmt = _apply_status_filter(stmt, status_filter)
    rows = list(
        (await db.execute(stmt.order_by(Decision.created_at.desc()))).scalars().all()
    )
    return await _decision_responses(db, rows)


async def attach_decisions_to_channel(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    channel_id: UUID,
) -> int:
    """Bind sender-team unscoped decisions to the interaction being handed off."""
    rows = (
        await db.execute(
            select(Decision).where(
                Decision.org_id == org_id,
                Decision.team_id == team_id,
                Decision.channel_id.is_(None),
                Decision.status.in_(("open", "proposed", "contested")),
            )
        )
    ).scalars().all()
    for d in rows:
        d.channel_id = channel_id
    if rows:
        await db.flush()
    return len(rows)
