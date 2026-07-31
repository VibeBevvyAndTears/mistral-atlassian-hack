"""Profiles HTTP router (M1-5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.lib.dependencies import DBSession, TenantScopeDep
from src.profiles import service as profiles_service
from src.tenancy.models import (
    ProfileData,
    ProfileDraftRequest,
    ProfileDraftResponse,
    ProfileResponse,
    ProfileVersionSummary,
)

router = APIRouter()


@router.get("/teams/{team_id}/profile", response_model=ProfileResponse)
async def get_profile(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> ProfileResponse:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await profiles_service.get_latest_profile(
        db, team_id=team_id, org_id=scope.org_id
    )


@router.put("/teams/{team_id}/profile", response_model=ProfileResponse)
async def put_profile(
    team_id: UUID,
    body: ProfileData,
    scope: TenantScopeDep,
    db: DBSession,
) -> ProfileResponse:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await profiles_service.put_profile(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        user_id=scope.user_id,
        actor_role=scope.role,
        data=body.data,
    )


@router.post(
    "/teams/{team_id}/profile/draft-from-document",
    response_model=ProfileDraftResponse,
)
async def draft_profile_from_document(
    team_id: UUID,
    body: ProfileDraftRequest,
    scope: TenantScopeDep,
    db: DBSession,
) -> ProfileDraftResponse:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await profiles_service.draft_profile_from_document(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        document_ids=body.document_ids,
        actor_role=scope.role,
    )


@router.get(
    "/teams/{team_id}/profile/versions",
    response_model=list[ProfileVersionSummary],
)
async def list_profile_versions(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[ProfileVersionSummary]:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await profiles_service.list_profile_versions(
        db, team_id=team_id, org_id=scope.org_id
    )


@router.get(
    "/teams/{team_id}/profile/versions/{version}",
    response_model=ProfileResponse,
)
async def get_profile_version(
    team_id: UUID,
    version: int,
    scope: TenantScopeDep,
    db: DBSession,
) -> ProfileResponse:
    if scope.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Team not found"
        )
    return await profiles_service.get_profile_version(
        db, team_id=team_id, org_id=scope.org_id, version=version
    )
