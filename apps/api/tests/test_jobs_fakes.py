"""Unit tests for FakeJobQueue (substrate S13)."""

from __future__ import annotations

import pytest

from src.jobs.fakes import FakeJobQueue
from src.jobs.queue import JobKind, JobState


@pytest.mark.asyncio
async def test_fake_job_queue_enqueue_claim_complete() -> None:
    q = FakeJobQueue()
    job_id = await q.enqueue(JobKind.ingest_document, {"document_id": "d1"})
    claimed = await q.claim_next("worker-1")
    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.state == JobState.running.value
    await q.complete_step(job_id, "parse", {"ok": True})
    assert claimed.completed_steps["parse"] == {"ok": True}


@pytest.mark.asyncio
async def test_fake_job_queue_dedupe() -> None:
    q = FakeJobQueue()
    a = await q.enqueue(JobKind.send_package, {"p": 1}, dedupe_key="pkg:1")
    b = await q.enqueue(JobKind.send_package, {"p": 2}, dedupe_key="pkg:1")
    assert a == b
