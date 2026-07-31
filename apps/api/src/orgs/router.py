"""Orgs HTTP router (M1-3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.lib.dependencies import CurrentUser, DBSession, TenantScopeDep
from src.orgs import service as orgs_service
from src.tenancy.models import AdminMetricsResponse, OrgCreate, OrgResponse

router = APIRouter()


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    user: CurrentUser,
    db: DBSession,
) -> OrgResponse:
    """Create an organization; caller becomes Org Owner."""
    return await orgs_service.create_org(db, user_id=UUID(user.id), name=body.name)


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
