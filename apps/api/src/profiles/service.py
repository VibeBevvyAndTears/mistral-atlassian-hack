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
    ProfileVersionSummary,
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
            detail="Only a Team Lead can make this change.",
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
    document_ids: list[UUID],
    actor_role: str,
) -> ProfileDraftResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Team Lead can make this change.",
        )

    documents = []
    for document_id in document_ids:
        document = await db.get(SourceDocument, document_id)
        if document is None or document.org_id != org_id or document.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )
        documents.append(document)

    filenames = [document.filename for document in documents]

    if settings.DATABASE_URL.startswith("sqlite") or not settings.MISTRAL_API_KEY:
        return ProfileDraftResponse(
            document_ids=[str(document.id) for document in documents],
            data=ProfileDraftData(
                purpose=f"Coordinate work described in {', '.join(filenames)}",
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
                    Claim.document_id.in_(document_ids),
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
        f"from documents {', '.join(repr(name) for name in filenames)} "
        "and these extracted claims:\n"
        + "\n".join(f"- {claim}" for claim in claims)
    )
    draft = await get_mistral_provider().generate_structured(prompt, ProfileDraftData)
    return ProfileDraftResponse(
        document_ids=[str(document.id) for document in documents],
        data=draft,
        generated_by="mistral",
    )


async def list_profile_versions(
    db: AsyncSession, *, team_id: UUID, org_id: UUID
) -> list[ProfileVersionSummary]:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    rows = await db.execute(
        select(TeamProfile.version, TeamProfile.created_at, TeamProfile.created_by)
        .where(TeamProfile.team_id == team_id)
        .order_by(TeamProfile.version.desc())
    )
    return [
        ProfileVersionSummary(
            version=version, created_at=created_at, created_by=str(created_by)
        )
        for version, created_at, created_by in rows.all()
    ]


async def get_profile_version(
    db: AsyncSession, *, team_id: UUID, org_id: UUID, version: int
) -> ProfileResponse:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )

    profile = await db.scalar(
        select(TeamProfile).where(
            TeamProfile.team_id == team_id, TeamProfile.version == version
        )
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile version not found"
        )
    return ProfileResponse(
        id=str(profile.id),
        team_id=str(profile.team_id),
        version=profile.version,
        data=dict(profile.data or {}),
        created_at=profile.created_at,
    )
