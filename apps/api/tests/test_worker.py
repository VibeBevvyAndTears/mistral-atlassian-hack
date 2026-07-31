"""Worker heartbeat + dead-letter unit tests (no Postgres)."""

from __future__ import annotations

import pytest

from src.jobs.fakes import FakeJobQueue
from src.jobs.queue import JobState
from src.jobs.worker import Worker


@pytest.mark.asyncio
async def test_worker_heartbeat_extends_lease() -> None:
    q = FakeJobQueue()
    job_id = await q.enqueue("ingest_document", {"doc": 1})
    claimed = await q.claim_next("w1", lease_seconds=60)
    assert claimed is not None
    assert await q.extend_lease(job_id, "w1", lease_seconds=60) is True
    assert await q.extend_lease(job_id, "other", lease_seconds=60) is False


@pytest.mark.asyncio
async def test_worker_reclaims_expired_running_lease() -> None:
    """§6.5 — crashed worker leaves running+expired lease; another worker reclaims."""
    q = FakeJobQueue()
    job_id = await q.enqueue("ingest_document", {})
    first = await q.claim_next("w1")
    assert first is not None
    assert first.attempts == 1
    await q.expire_lease(job_id)
    # Still "running" but lease gone — must be reclaimable
    assert q.jobs[job_id].state == JobState.running.value
    second = await q.claim_next("w2")
    assert second is not None
    assert second.id == job_id
    assert second.attempts == 2
    assert await q.extend_lease(job_id, "w2") is True
    assert await q.extend_lease(job_id, "w1") is False


@pytest.mark.asyncio
async def test_terminal_ops_fenced_by_lease_owner() -> None:
    """Losing worker must not fail_step/mark_completed after reclaim."""
    q = FakeJobQueue()
    job_id = await q.enqueue("ingest_document", {})
    await q.claim_next("w1")
    await q.expire_lease(job_id)
    await q.claim_next("w2")
    assert await q.fail_step(
        job_id, "handler", "stale", retry=True, worker_id="w1"
    ) is False
    assert q.jobs[job_id].state == JobState.running.value
    assert await q.mark_completed(job_id, worker_id="w1") is False
    assert await q.mark_completed(job_id, worker_id="w2") is True
    assert q.jobs[job_id].state == JobState.completed.value


@pytest.mark.asyncio
async def test_worker_dead_letter_after_five_attempts() -> None:
    q = FakeJobQueue(max_attempts=5)
    job_id = await q.enqueue("unknown_kind", {})
    for i in range(5):
        claimed = await q.claim_next("w1")
        assert claimed is not None
        assert claimed.attempts == i + 1
        retry = claimed.attempts < q.max_attempts
        await q.fail_step(job_id, "dispatch", "no handler", retry=retry)
        if retry:
            assert q.jobs[job_id].state == JobState.pending.value
        else:
            assert q.jobs[job_id].state == JobState.dead.value
    assert q.jobs[job_id].state == JobState.dead.value


def test_worker_default_heartbeat_interval() -> None:
    # Construction without DB — only validates §6.5 ~10s heartbeat config
    w = Worker(session_factory=None)  # type: ignore[arg-type]
    assert w.heartbeat_interval_seconds == 10.0
    assert w.lease_seconds == 60
