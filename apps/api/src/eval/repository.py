"""Data-access operations for org-scoped evaluation goldens."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.eval.models import GoldenExample


async def list_goldens(db: AsyncSession, org_id: UUID) -> list[GoldenExample]:
    result = await db.execute(
        select(GoldenExample)
        .where(GoldenExample.org_id == org_id)
        .order_by(GoldenExample.created_at.desc())
    )
    return list(result.scalars().all())


async def get_golden(
    db: AsyncSession, org_id: UUID, golden_id: UUID
) -> GoldenExample | None:
    result = await db.execute(
        select(GoldenExample).where(
            GoldenExample.id == golden_id, GoldenExample.org_id == org_id
        )
    )
    return result.scalar_one_or_none()


async def create_golden(db: AsyncSession, golden: GoldenExample) -> GoldenExample:
    db.add(golden)
    await db.flush()
    await db.refresh(golden)
    return golden


async def delete_golden(db: AsyncSession, golden: GoldenExample) -> None:
    await db.delete(golden)
    await db.flush()
