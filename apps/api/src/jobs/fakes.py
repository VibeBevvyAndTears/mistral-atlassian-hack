"""Test doubles for the job queue (substrate S13 — FakeJobQueue only)."""

from __future__ import annotations

import uuid as uuid_lib
from dataclasses import dataclass, field
from typing import Any

from src.jobs.queue import Job, JobKind, JobState


@dataclass
class FakeJobQueue:
    """In-memory job queue for unit tests — no Postgres required."""

    jobs: dict[uuid_lib.UUID, Job] = field(default_factory=dict)
    steps: dict[uuid_lib.UUID, dict[str, Any]] = field(default_factory=dict)
    enqueued: list[tuple[str, dict[str, Any], str | None]] = field(default_factory=list)
    leases: dict[uuid_lib.UUID, tuple[str, int]] = field(default_factory=dict)
    max_attempts: int = 5

    async def enqueue(
        self,
        kind: JobKind | str,
        payload: dict[str, Any],
        *,
        dedupe_key: str | None = None,
    ) -> uuid_lib.UUID:
        kind_value = kind.value if isinstance(kind, JobKind) else kind
        if dedupe_key:
            for job in self.jobs.values():
                if job.state in (JobState.pending.value, JobState.running.value):  # noqa: SIM102
                    # Fake stores dedupe on payload for simplicity
                    if job.payload.get("_dedupe_key") == dedupe_key:
                        return job.id
        job_id = uuid_lib.uuid4()
        payload_with_key = {**payload, "_dedupe_key": dedupe_key}
        self.jobs[job_id] = Job(
            id=job_id,
            kind=kind_value,
            payload=payload_with_key,
            state=JobState.pending.value,
            attempts=0,
            max_attempts=self.max_attempts,
            completed_steps={},
        )
        self.steps[job_id] = {}
        self.enqueued.append((kind_value, payload, dedupe_key))
        return job_id

    async def claim_next(self, worker_id: str, lease_seconds: int = 60) -> Job | None:
        """Claim pending jobs, or reclaim running jobs whose lease expired (§6.5)."""
        for job in self.jobs.values():
            expired_running = (
                job.state == JobState.running.value and job.id not in self.leases
            )
            if job.state == JobState.pending.value or expired_running:
                job.state = JobState.running.value
                job.attempts += 1
                self.leases[job.id] = (worker_id, lease_seconds)
                return job
        return None

    async def expire_lease(self, job_id: uuid_lib.UUID) -> None:
        """Simulate locked_until expiry (worker crash) without changing state."""
        self.leases.pop(job_id, None)

    async def extend_lease(
        self, job_id: uuid_lib.UUID, worker_id: str, lease_seconds: int = 60
    ) -> bool:
        lease = self.leases.get(job_id)
        job = self.jobs.get(job_id)
        if lease is None or job is None:
            return False
        if lease[0] != worker_id or job.state != JobState.running.value:
            return False
        self.leases[job_id] = (worker_id, lease_seconds)
        return True

    async def complete_step(
        self, job_id: uuid_lib.UUID, step: str, result: dict[str, Any]
    ) -> None:
        steps = self.steps.setdefault(job_id, {})
        if step in steps:
            return
        steps[step] = result
        if job_id in self.jobs:
            self.jobs[job_id].completed_steps = dict(steps)

    async def fail_step(
        self,
        job_id: uuid_lib.UUID,
        step: str,
        error: str,
        *,
        retry: bool,
        worker_id: str | None = None,
    ) -> bool:
        job = self.jobs.get(job_id)
        if job is None:
            return False
        lease = self.leases.get(job_id)
        if worker_id is not None and (lease is None or lease[0] != worker_id):
            return False
        if retry and job.attempts < self.max_attempts:
            job.state = JobState.pending.value
            self.leases.pop(job_id, None)
        else:
            job.state = JobState.dead.value
            self.leases.pop(job_id, None)
        job.completed_steps = {**job.completed_steps, f"error:{step}": error}
        return True

    async def mark_completed(
        self, job_id: uuid_lib.UUID, *, worker_id: str | None = None
    ) -> bool:
        job = self.jobs.get(job_id)
        if job is None:
            return False
        lease = self.leases.get(job_id)
        if worker_id is not None and (lease is None or lease[0] != worker_id):
            return False
        job.state = JobState.completed.value
        self.leases.pop(job_id, None)
        return True
