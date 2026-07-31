"""Team profile versioning service (M1-5)."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import get_mistral_provider
from src.graph.models import Claim
from src.lib.config import settings
from src.tenancy.models import (
    ProfileDraftData,
    ProfileDraftResponse,
    ProfileResponse,
    SourceDocument,
    Team,
    TeamProfile,
)


async def get_latest_profile(
    db: AsyncSession, *, team_id: UUID, org_id: UUID
) -> ProfileResponse:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    profile = await db.scalar(
        select(TeamProfile)
        .where(TeamProfile.team_id == team_id)
        .order_by(TeamProfile.version.desc())
        .limit(1)
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        )
    return ProfileResponse(
        id=str(profile.id),
        team_id=str(profile.team_id),
        version=profile.version,
        data=dict(profile.data or {}),
        created_at=profile.created_at,
    )


async def put_profile(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    user_id: UUID,
    actor_role: str,
    data: dict[str, Any],
) -> ProfileResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    max_version = await db.scalar(
        select(func.coalesce(func.max(TeamProfile.version), 0)).where(
            TeamProfile.team_id == team_id
        )
    )
    next_version = int(max_version or 0) + 1
    profile = TeamProfile(
        id=uuid.uuid4(),
        team_id=team_id,
        version=next_version,
        data=data,
        created_by=user_id,
    )
    db.add(profile)
    await db.flush()
    return ProfileResponse(
        id=str(profile.id),
        team_id=str(profile.team_id),
        version=profile.version,
        data=dict(profile.data or {}),
        created_at=profile.created_at,
    )


async def draft_profile_from_document(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    document_id: UUID,
    actor_role: str,
) -> ProfileDraftResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )
    document = await db.get(SourceDocument, document_id)
    if document is None or document.org_id != org_id or document.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )

    if settings.DATABASE_URL.startswith("sqlite") or not settings.MISTRAL_API_KEY:
        return ProfileDraftResponse(
            document_id=str(document.id),
            data=ProfileDraftData(
                purpose=f"Coordinate work described in {document.filename}",
                audiences=["cross-functional partners"],
                tone="clear and concise",
                communication_preferences=["define acronyms", "highlight decisions"],
                known_terms=[],
            ),
            generated_by="deterministic_stub",
        )

    claims = (
        (
            await db.execute(
                select(Claim.text)
                .where(
                    Claim.org_id == org_id,
                    Claim.team_id == team_id,
                    Claim.document_id == document_id,
                )
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    prompt = (
        "Draft a team communication profile for Lead review. Do not invent facts. "
        "Infer purpose, audiences, tone, communication preferences, and known terms "
        f"from document {document.filename!r} and these extracted claims:\n"
        + "\n".join(f"- {claim}" for claim in claims)
    )
    draft = await get_mistral_provider().generate_structured(prompt, ProfileDraftData)
    return ProfileDraftResponse(
        document_id=str(document.id),
        data=draft,
        generated_by="mistral",
    )
