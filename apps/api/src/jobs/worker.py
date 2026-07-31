"""Long-lived job polling worker (S8) — lease heartbeat + dead-letter after 5."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.jobs import queue as job_queue

logger = logging.getLogger(__name__)

KindHandler = Callable[[job_queue.Job, AsyncSession], Awaitable[None]]


@dataclass
class Worker:
    """Polls job_queue, heartbeats lease (~10s), dead-letters after max attempts."""

    session_factory: async_sessionmaker[AsyncSession]
    worker_id: str = field(default_factory=lambda: f"worker-{uuid.uuid4().hex[:8]}")
    handlers: dict[str, KindHandler] = field(default_factory=dict)
    poll_interval_seconds: float = 1.0
    heartbeat_interval_seconds: float = 10.0
    lease_seconds: int = 60
    _stop: asyncio.Event = field(default_factory=asyncio.Event)

    def stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        while not self._stop.is_set():
            processed = await self.run_once()
            if not processed:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_interval_seconds
                    )

    async def run_once(self) -> bool:
        """Claim and process one job. Returns True if a job was claimed."""
        async with self.session_factory() as session:
            job = await job_queue.claim_next(
                session, self.worker_id, lease_seconds=self.lease_seconds
            )
            await session.commit()
            if job is None:
                return False

        await self._process_job(job)
        return True

    async def _process_job(self, job: job_queue.Job) -> None:
        handler = self.handlers.get(job.kind)
        lease_lost = asyncio.Event()
        heartbeat = asyncio.create_task(self._heartbeat_loop(job.id, lease_lost))
        try:
            if handler is None:
                if lease_lost.is_set():
                    return
                async with self.session_factory() as session:
                    await job_queue.fail_step(
                        session,
                        job.id,
                        "dispatch",
                        f"no handler for kind={job.kind}",
                        retry=job.attempts < job.max_attempts,
                        worker_id=self.worker_id,
                    )
                    await session.commit()
                return

            async with self.session_factory() as session:
                try:
                    if lease_lost.is_set():
                        return
                    await handler(job, session)
                    if lease_lost.is_set():
                        await session.rollback()
                        return
                    await job_queue.mark_completed(
                        session, job.id, worker_id=self.worker_id
                    )
                    await session.commit()
                except Exception as exc:
                    logger.exception("job %s failed: %s", job.id, exc)
                    await session.rollback()
                    if lease_lost.is_set():
                        return
                    async with self.session_factory() as fail_session:
                        await job_queue.fail_step(
                            fail_session,
                            job.id,
                            "handler",
                            str(exc),
                            retry=job.attempts < job.max_attempts,
                            worker_id=self.worker_id,
                        )
                        await fail_session.commit()
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat_loop(
        self, job_id: uuid.UUID, lease_lost: asyncio.Event
    ) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_interval_seconds)
            async with self.session_factory() as session:
                ok = await job_queue.extend_lease(
                    session,
                    job_id,
                    self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
                await session.commit()
                if not ok:
                    lease_lost.set()
                    return
