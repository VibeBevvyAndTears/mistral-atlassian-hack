"""Orgs HTTP router (M1-3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.lib.dependencies import CurrentUser, DBSession, TenantScopeDep
from src.orgs import service as orgs_service
from src.tenancy.models import (
    AdminMetricsResponse,
    MyOrgMembership,
    OrgCreate,
    OrgResponse,
)

router = APIRouter()


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    user: CurrentUser,
    db: DBSession,
) -> OrgResponse:
    """Create an organization; caller becomes Org Owner."""
    return await orgs_service.create_org(db, user_id=UUID(user.id), name=body.name)


@router.get("", response_model=list[MyOrgMembership])
async def list_my_orgs(
    user: CurrentUser,
    db: DBSession,
) -> list[MyOrgMembership]:
    """List orgs (with nested teams) the current user belongs to."""
    return await orgs_service.list_my_orgs(db, user_id=UUID(user.id))


@router.post("/{org_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_org(
    org_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> None:
    """Archive an org — owner only. Reversible: data is kept, just hidden."""
    if scope.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    await orgs_service.archive_org(db, org_id=org_id, actor_role=scope.role)


@router.get("/{org_id}/admin/metrics", response_model=AdminMetricsResponse)
async def get_admin_metrics(
    org_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
) -> AdminMetricsResponse:
    if scope.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return await orgs_service.get_admin_metrics(
        db,
        org_id=org_id,
        actor_role=scope.role,
    )
