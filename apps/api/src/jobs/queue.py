"""Postgres job queue models and API (substrate S7)."""

from __future__ import annotations

import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, func, select, text, update
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.lib.database import Base

# Portable JSON: Postgres uses JSONB; SQLite (tests) uses JSON.
_JsonPayload = JSONB().with_variant(JSON(), "sqlite")


class JobKind(StrEnum):
    ingest_document = "ingest_document"
    send_package = "send_package"
    regenerate_rendition = "regenerate_rendition"


class JobState(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    dead = "dead"


class JobQueue(Base):
    """Postgres-backed durable job row."""

    __tablename__ = "job_queue"

    id: Mapped[uuid_lib.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        _JsonPayload, nullable=False, default=dict
    )
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobState.pending.value, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    dedupe_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # noqa: E501
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_steps: Mapped[dict[str, Any]] = mapped_column(
        _JsonPayload, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Job(BaseModel):
    """Lightweight job view returned by claim_next."""

    id: uuid_lib.UUID
    kind: str
    payload: dict[str, Any]
    state: str
    attempts: int
    max_attempts: int = 5
    completed_steps: dict[str, Any] = Field(default_factory=dict)


async def enqueue(
    session: AsyncSession,
    kind: JobKind | str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
) -> uuid_lib.UUID:
    """Enqueue a job. If dedupe_key matches a pending/running job, return that id."""
    kind_value = kind.value if isinstance(kind, JobKind) else kind
    if dedupe_key:
        existing = await session.scalar(
            select(JobQueue).where(
                JobQueue.dedupe_key == dedupe_key,
                JobQueue.state.in_([JobState.pending.value, JobState.running.value]),
            )
        )
        if existing is not None:
            return existing.id

    job = JobQueue(
        id=uuid_lib.uuid4(),
        kind=kind_value,
        payload=payload,
        state=JobState.pending.value,
        dedupe_key=dedupe_key,
        next_run_at=datetime.now(UTC),
        completed_steps={},
    )
    session.add(job)
    await session.flush()
    return job.id


async def claim_next(
    session: AsyncSession,
    worker_id: str,
    lease_seconds: int = 60,
) -> Job | None:
    """Claim the next runnable job using SKIP LOCKED."""
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=lease_seconds)

    result = await session.execute(
        text(
            """
            SELECT id FROM job_queue
            WHERE (
                state = 'pending'
                OR (state = 'running' AND locked_until IS NOT NULL AND locked_until < :now)
              )
              AND (next_run_at IS NULL OR next_run_at <= :now)
              AND (locked_until IS NULL OR locked_until < :now)
            ORDER BY created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """  # noqa: E501
        ),
        {"now": now},
    )
    row = result.first()
    if row is None:
        return None

    job_id = row[0]
    await session.execute(
        update(JobQueue)
        .where(JobQueue.id == job_id)
        .values(
            state=JobState.running.value,
            locked_by=worker_id,
            locked_until=lease_until,
            attempts=JobQueue.attempts + 1,
            updated_at=now,
        )
    )
    job = await session.get(JobQueue, job_id)
    if job is None:
        return None
    return Job(
        id=job.id,
        kind=job.kind,
        payload=job.payload,
        state=job.state,
        attempts=job.attempts,
        max_attempts=job.max_attempts,
        completed_steps=dict(job.completed_steps or {}),
    )


async def complete_step(
    session: AsyncSession,
    job_id: uuid_lib.UUID,
    step: str,
    result: dict[str, Any],
) -> None:
    """Idempotent UPSERT of a completed step keyed by (job_id, step)."""
    job = await session.get(JobQueue, job_id)
    if job is None:
        return
    steps = dict(job.completed_steps or {})
    if step in steps:
        return
    steps[step] = result
    job.completed_steps = steps
    job.updated_at = datetime.now(UTC)
    await session.flush()


async def fail_step(
    session: AsyncSession,
    job_id: uuid_lib.UUID,
    step: str,
    error: str,
    *,
    retry: bool,
    worker_id: str | None = None,
) -> bool:
    """Record a step failure; optionally re-queue or dead-letter.

    When ``worker_id`` is set, no-ops unless this worker still holds the lease
    (prevents dual-writer after §6.5 reclaim).
    """
    job = await session.get(JobQueue, job_id)
    if job is None:
        return False
    if worker_id is not None and job.locked_by != worker_id:
        return False
    now = datetime.now(UTC)
    job.last_error = f"{step}: {error}"
    job.locked_by = None
    job.locked_until = None
    job.updated_at = now
    if retry and job.attempts < job.max_attempts:
        job.state = JobState.pending.value
        job.next_run_at = now + timedelta(seconds=min(2**job.attempts, 300))
    else:
        job.state = JobState.dead.value
    await session.flush()
    return True


async def mark_completed(
    session: AsyncSession,
    job_id: uuid_lib.UUID,
    *,
    worker_id: str | None = None,
) -> bool:
    """Mark the whole job completed.

    When ``worker_id`` is set, no-ops unless this worker still holds the lease.
    """
    job = await session.get(JobQueue, job_id)
    if job is None:
        return False
    if worker_id is not None and job.locked_by != worker_id:
        return False
    job.state = JobState.completed.value
    job.locked_by = None
    job.locked_until = None
    job.updated_at = datetime.now(UTC)
    await session.flush()
    return True


async def extend_lease(
    session: AsyncSession,
    job_id: uuid_lib.UUID,
    worker_id: str,
    lease_seconds: int = 60,
) -> bool:
    """Heartbeat: extend locked_until for a job held by this worker (§6.5 lease)."""
    now = datetime.now(UTC)
    result = await session.execute(
        update(JobQueue)
        .where(
            JobQueue.id == job_id,
            JobQueue.locked_by == worker_id,
            JobQueue.state == JobState.running.value,
        )
        .values(
            locked_until=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
    )
    await session.flush()
    return bool(result.rowcount)
