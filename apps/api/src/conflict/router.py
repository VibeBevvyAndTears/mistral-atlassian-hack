"""Conflict review + decisions HTTP API (M3)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.conflict import service as conflict_service
from src.conflict.models import (
    DecisionResponse,
    ProposeResolutionRequest,
    ResolveReviewRequest,
    ReviewItemResponse,
)
from src.lib.dependencies import DBSession, TenantScopeDep

router = APIRouter()


@router.get("/teams/{team_id}/review-items", response_model=list[ReviewItemResponse])
async def list_review_items(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[ReviewItemResponse]:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await conflict_service.list_review_items(
        db, org_id=scope.org_id, team_id=team_id, status_filter=status_filter
    )


@router.post("/review-items/{item_id}/propose", response_model=ReviewItemResponse)
async def propose_resolution(
    item_id: UUID,
    body: ProposeResolutionRequest,
    scope: TenantScopeDep,
    db: DBSession,
) -> ReviewItemResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")  # noqa: E501
    return await conflict_service.propose_resolution(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        item_id=item_id,
        user_id=scope.user_id,
        resolution=body.resolution,
    )


@router.post("/review-items/{item_id}/resolve", response_model=ReviewItemResponse)
async def resolve_review_item(
    item_id: UUID,
    body: ResolveReviewRequest,
    scope: TenantScopeDep,
    db: DBSession,
) -> ReviewItemResponse:
    if scope.team_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found")  # noqa: E501
    return await conflict_service.resolve_review_item(
        db,
        org_id=scope.org_id,
        team_id=scope.team_id,
        item_id=item_id,
        user_id=scope.user_id,
        resolution=body.resolution,
        actor_role=scope.role,
    )


@router.get("/teams/{team_id}/decisions", response_model=list[DecisionResponse])
async def list_team_decisions(
    team_id: UUID,
    scope: TenantScopeDep,
    db: DBSession,
    status_filter: str | None = Query(default="all", alias="status"),
) -> list[DecisionResponse]:
    if scope.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")  # noqa: E501
    return await conflict_service.list_decisions(
        db, org_id=scope.org_id, team_id=team_id, status_filter=status_filter
    )
