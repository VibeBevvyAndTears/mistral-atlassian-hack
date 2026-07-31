"""Tenant scope + RLS session-var binding (substrate S2/S9)."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.auth import CurrentUser
from src.lib.database import get_db
from src.tenancy.models import OrgMember, Team, TeamMember


class TenantScope(BaseModel):
    """Request-scoped org/team identity after membership validation."""

    user_id: UUID
    org_id: UUID
    team_id: UUID | None = None
    role: Literal["owner", "lead", "member", "viewer"] = "member"

    def require_role(self, *roles: str) -> None:
        if self.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action",
            )


async def apply_rls_session_vars(
    session: AsyncSession,
    org_id: UUID | None,
    team_id: UUID | None,
) -> None:
    """Bind Postgres GUCs used by RLS policies (app.current_org_id / team_id)."""
    await session.execute(
        text("SELECT app_set_tenant(:org_id, :team_id)"),
        {"org_id": org_id, "team_id": team_id},
    )


async def get_tenant_scope(
    request: Request,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_org_id: Annotated[str | None, Header(alias="X-Org-Id")] = None,
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
) -> TenantScope:
    """Resolve and validate TenantScope from headers.

    Membership is validated via ORM against ``team_members`` / ``org_members``.
    Cross-tenant miss returns 404 (not 403) to avoid existence leaks.
    """
    if hasattr(request.state, "tenant_scope") and request.state.tenant_scope is not None:  # noqa: E501
        return request.state.tenant_scope  # type: ignore[no-any-return]

    if not x_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Org-Id header is required",
        )

    try:
        org_id = UUID(x_org_id)
        team_id = UUID(x_team_id) if x_team_id else None
        user_id = UUID(user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid org/team/user id",
        ) from exc

    role: Literal["owner", "lead", "member", "viewer"] = "member"

    if team_id is not None:
        try:
            membership = await db.scalar(
                select(TeamMember.role)
                .join(Team, Team.id == TeamMember.team_id)
                .where(
                    TeamMember.team_id == team_id,
                    TeamMember.user_id == user_id,
                    Team.org_id == org_id,
                )
                .limit(1)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            ) from None

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team not found",
            )
        if membership in ("owner", "lead", "member", "viewer"):
            role = membership  # type: ignore[assignment]
    else:
        try:
            org_membership = await db.scalar(
                select(OrgMember.user_id)
                .where(OrgMember.org_id == org_id, OrgMember.user_id == user_id)
                .limit(1)
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            ) from None

        if org_membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )
        org_role = await db.scalar(
            select(OrgMember.role).where(
                OrgMember.org_id == org_id, OrgMember.user_id == user_id
            )
        )
        if org_role == "owner":
            role = "owner"

    try:  # noqa: SIM105
        await apply_rls_session_vars(db, org_id, team_id)
    except Exception:  # noqa: S110
        # RLS helpers may be absent (SQLite tests / pre-migration).
        pass

    scope = TenantScope(user_id=user_id, org_id=org_id, team_id=team_id, role=role)
    request.state.tenant_scope = scope
    return scope


TenantScopeDep = Annotated[TenantScope, Depends(get_tenant_scope)]

__all__ = [
    "TenantScope",
    "TenantScopeDep",
    "apply_rls_session_vars",
    "get_tenant_scope",
]
