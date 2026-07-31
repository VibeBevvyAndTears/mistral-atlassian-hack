"""Notification producer + list (M1-12 / FR-8 scaffolding)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.tenancy.models import Notification


class NotificationResponse(BaseModel):
    id: str
    org_id: str
    user_id: str
    kind: str
    payload: dict[str, Any]
    read_at: datetime | None = None
    created_at: datetime


async def create_notification(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> Notification:
    """Insert a notification row (Realtime consumers pick up INSERT)."""
    row = Notification(
        id=uuid.uuid4(),
        org_id=org_id,
        user_id=user_id,
        kind=kind,
        payload=payload or {},
    )
    db.add(row)
    await db.flush()
    return row


async def list_notifications(
    db: AsyncSession,
    *,
    org_id: UUID,
    user_id: UUID,
    unread_only: bool = False,
    limit: int = 50,
) -> list[NotificationResponse]:
    stmt = (
        select(Notification)
        .where(Notification.org_id == org_id, Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(min(limit, 100))
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        NotificationResponse(
            id=str(r.id),
            org_id=str(r.org_id),
            user_id=str(r.user_id),
            kind=r.kind,
            payload=r.payload or {},
            read_at=r.read_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


class NotificationListQuery(BaseModel):
    unread_only: bool = False
    limit: int = Field(default=50, ge=1, le=100)
