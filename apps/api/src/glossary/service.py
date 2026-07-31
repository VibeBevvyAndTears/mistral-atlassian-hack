"""Team glossary business logic."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.glossary.models import (
    GlossaryKind,
    GlossaryTerm,
    GlossaryTermResponse,
)
from src.tenancy.models import Team


def _require_lead(role: str) -> None:
    if role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )


async def _require_team(db: AsyncSession, *, org_id: UUID, team_id: UUID) -> None:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )


def _response(row: GlossaryTerm) -> GlossaryTermResponse:
    return GlossaryTermResponse(
        id=str(row.id),
        team_id=str(row.team_id),
        term=row.term,
        definition=row.definition,
        kind=row.kind,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_terms(
    db: AsyncSession, *, org_id: UUID, team_id: UUID
) -> list[GlossaryTermResponse]:
    await _require_team(db, org_id=org_id, team_id=team_id)
    rows = (
        (
            await db.execute(
                select(GlossaryTerm)
                .where(GlossaryTerm.org_id == org_id, GlossaryTerm.team_id == team_id)
                .order_by(GlossaryTerm.term.asc())
            )
        )
        .scalars()
        .all()
    )
    return [_response(row) for row in rows]


async def create_term(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    actor_role: str,
    term: str,
    definition: str,
    kind: GlossaryKind,
) -> GlossaryTermResponse:
    _require_lead(actor_role)
    await _require_team(db, org_id=org_id, team_id=team_id)
    row = GlossaryTerm(
        id=uuid.uuid4(),
        org_id=org_id,
        team_id=team_id,
        term=term.strip(),
        definition=definition.strip(),
        kind=kind,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Glossary term already exists",
        ) from None
    return _response(row)


async def update_term(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    term_id: UUID,
    actor_role: str,
    term: str | None,
    definition: str | None,
    kind: GlossaryKind | None,
) -> GlossaryTermResponse:
    _require_lead(actor_role)
    row = await db.get(GlossaryTerm, term_id)
    if row is None or row.org_id != org_id or row.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found"
        )
    if term is not None:
        row.term = term.strip()
    if definition is not None:
        row.definition = definition.strip()
    if kind is not None:
        row.kind = kind
    row.updated_at = datetime.now(UTC)
    try:
        await db.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Glossary term already exists",
        ) from None
    return _response(row)


async def delete_term(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    term_id: UUID,
    actor_role: str,
) -> None:
    _require_lead(actor_role)
    row = await db.get(GlossaryTerm, term_id)
    if row is None or row.org_id != org_id or row.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Glossary term not found"
        )
    await db.delete(row)
    await db.flush()
