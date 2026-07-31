"""Teams HTTP router (M1-4)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from src.lib.dependencies import CurrentUser, DBSession, TenantScopeDep
from src.teams import service as teams_service
from src.tenancy.models import (
    InviteAcceptRequest,
    InviteCreate,
    InviteResponse,
    TeamCreate,
    TeamResponse,
)
from src.users.model import User

router = APIRouter()


@router.post(
    "/orgs/{org_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    org_id: UUID,
    body: TeamCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> TeamResponse:
    if scope.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")  # noqa: E501
    return await teams_service.create_team(
        db, org_id=org_id, user_id=scope.user_id, name=body.name
    )


@router.post(
    "/teams/{team_id}/invites",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    team_id: UUID,
    body: InviteCreate,
    scope: TenantScopeDep,
    db: DBSession,
) -> InviteResponse:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await teams_service.create_invite(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        actor_user_id=scope.user_id,
        actor_role=scope.role,
        email=body.email,
        username=body.username,
        role=body.role,
    )


@router.post("/invites/accept", response_model=InviteResponse)
async def accept_invite(
    body: InviteAcceptRequest,
    user: CurrentUser,
    db: DBSession,
) -> InviteResponse:
    result = await db.execute(select(User).where(User.id == UUID(user.id)))
    db_user = result.scalar_one_or_none()
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")  # noqa: E501
    return await teams_service.accept_invite(
        db,
        token=body.token,
        user_id=UUID(user.id),
        user_email=db_user.email,
    )


@router.post(
    "/teams/{team_id}/members/{user_id}/remove",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> None:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    await teams_service.remove_member(
        db,
        team_id=team_id,
        org_id=scope.org_id,
        target_user_id=user_id,
        actor_role=scope.role,
    )


@router.get("/teams/{team_id}/members")
async def list_members(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> list[dict[str, str]]:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await teams_service.list_members(
        db, team_id=team_id, org_id=scope.org_id
    )
