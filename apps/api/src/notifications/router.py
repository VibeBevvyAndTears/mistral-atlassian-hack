"""Notifications HTTP router."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.lib.dependencies import DBSession, TenantScopeDep
from src.notifications import service as notifications_service
from src.notifications.service import NotificationResponse

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    scope: TenantScopeDep,
    db: DBSession,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[NotificationResponse]:
    """List notifications for the authenticated user within the active org."""
    return await notifications_service.list_notifications(
        db,
        org_id=scope.org_id,
        user_id=scope.user_id,
        unread_only=unread_only,
        limit=limit,
    )
