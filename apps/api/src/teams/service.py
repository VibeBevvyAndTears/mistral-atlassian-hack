"""Teams + invites service (M1-4)."""

from __future__ import annotations

import secrets
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.auth import normalize_email, normalize_username, validate_username
from src.lib.token_store import revoke_user_tokens
from src.orgs.service import get_org_member_role
from src.tenancy.models import (
    Invite,
    InviteResponse,
    OrgMember,
    Team,
    TeamMember,
    TeamResponse,
)
from src.users.model import User


async def create_team(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    name: str,
) -> TeamResponse:
    role = await get_org_member_role(db, org_id=org_id, user_id=user_id)
    if role != "owner":
        # Existence-safe: non-members already 404 via TenantScope; members who
        # aren't owner get 403 for insufficient role (known membership).
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")  # noqa: E501
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )
    team = Team(id=uuid.uuid4(), org_id=org_id, name=name)
    db.add(team)
    db.add(TeamMember(team_id=team.id, user_id=user_id, role="lead"))
    await db.flush()
    return TeamResponse(
        id=str(team.id), org_id=str(team.org_id), name=team.name, created_at=team.created_at  # noqa: E501
    )


async def _resolve_invite_email(
    db: AsyncSession,
    *,
    email: str | None,
    username: str | None,
) -> tuple[str, User | None]:
    """Resolve invite target to an email + optional existing user."""
    if not email and not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide email or username",
        )

    target: User | None = None
    resolved_email: str | None = None

    if username:
        handle = validate_username(username)
        target = await db.scalar(select(User).where(User.username == handle))
        if target is None and not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Username not found",
            )
        if target is not None:
            resolved_email = target.email

    if email:
        resolved_email = normalize_email(email)
        by_email = await db.scalar(select(User).where(User.email == resolved_email))
        if by_email is not None:
            target = by_email
            if username and target.username and target.username != normalize_username(username):  # noqa: E501
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email and username refer to different users",
                )

    if not resolved_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve invite email",
        )
    return resolved_email, target


async def create_invite(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    actor_user_id: UUID,
    actor_role: str,
    email: str | None,
    username: str | None,
    role: str,
) -> InviteResponse:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501

    resolved_email, target = await _resolve_invite_email(db, email=email, username=username)  # noqa: E501
    invite_role = role if role in ("lead", "member", "viewer") else "member"

    invite = Invite(
        id=uuid.uuid4(),
        team_id=team_id,
        email=resolved_email,
        role=invite_role,
        token=secrets.token_urlsafe(24),
        created_by=actor_user_id,
    )
    db.add(invite)
    await db.flush()

    added_immediately = False
    if target is not None:
        await _ensure_memberships(
            db,
            org_id=org_id,
            team_id=team_id,
            user_id=target.id,
            role=invite_role,
        )
        added_immediately = True

    return InviteResponse(
        id=str(invite.id),
        team_id=str(invite.team_id),
        email=invite.email,
        role=invite.role,
        token=invite.token,
        created_at=invite.created_at,
        added_immediately=added_immediately,
    )


async def _ensure_memberships(
    db: AsyncSession,
    *,
    org_id: UUID,
    team_id: UUID,
    user_id: UUID,
    role: str,
) -> None:
    org_member = await db.get(OrgMember, {"org_id": org_id, "user_id": user_id})
    if org_member is None:
        db.add(OrgMember(org_id=org_id, user_id=user_id, role="member"))

    team_member = await db.get(TeamMember, {"team_id": team_id, "user_id": user_id})
    if team_member is None:
        db.add(TeamMember(team_id=team_id, user_id=user_id, role=role))
    await db.flush()


async def accept_invite(
    db: AsyncSession,
    *,
    token: str,
    user_id: UUID,
    user_email: str,
) -> InviteResponse:
    invite = await db.scalar(select(Invite).where(Invite.token == token))
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")  # noqa: E501

    if normalize_email(invite.email) != normalize_email(user_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite email does not match the signed-in user",
        )

    team = await db.get(Team, invite.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501

    await _ensure_memberships(
        db,
        org_id=team.org_id,
        team_id=team.id,
        user_id=user_id,
        role=invite.role,
    )

    return InviteResponse(
        id=str(invite.id),
        team_id=str(invite.team_id),
        email=invite.email,
        role=invite.role,
        token=invite.token,
        created_at=invite.created_at,
        added_immediately=True,
    )


async def remove_member(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
    target_user_id: UUID,
    actor_role: str,
) -> None:
    if actor_role not in ("owner", "lead"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role for this action",
        )
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501

    member = await db.get(TeamMember, {"team_id": team_id, "user_id": target_user_id})
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")  # noqa: E501

    await db.delete(member)
    await db.flush()
    await revoke_user_tokens(str(target_user_id))


async def list_members(
    db: AsyncSession,
    *,
    team_id: UUID,
    org_id: UUID,
) -> list[dict[str, str]]:
    team = await db.get(Team, team_id)
    if team is None or team.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501

    rows = await db.execute(
        select(TeamMember.user_id, TeamMember.role, User.email, User.username)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team_id)
    )
    return [
        {
            "user_id": str(uid),
            "role": role,
            "email": email,
            "username": username or "",
        }
        for uid, role, email, username in rows.all()
    ]
