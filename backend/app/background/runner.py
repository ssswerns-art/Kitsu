import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

JobHandler = Callable[[], Awaitable[None]]


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class Job:
    key: str
    handler: JobHandler
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    attempts: int = 0


class JobRunner:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._statuses: dict[str, JobStatus] = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("kitsu.jobs")

    def status_for(self, key: str) -> JobStatus | None:
        return self._statuses.get(key)

    async def enqueue(self, job: Job) -> Job:
        async with self._lock:
            status = self._statuses.get(job.key)
            if status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED}:
                return job

            self._statuses[job.key] = JobStatus.QUEUED
            await self._queue.put(job)
            await self._ensure_worker()

        return job

    async def drain(self) -> None:
        await self._queue.join()

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _ensure_worker(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        try:
            while True:
                job = await self._queue.get()
                await self._run_job(job)
                self._queue.task_done()
        except asyncio.CancelledError:
            return

    async def _run_job(self, job: Job) -> None:
        self._statuses[job.key] = JobStatus.RUNNING
        while job.attempts < job.max_attempts:
            try:
                await job.handler()
            except Exception as exc:  # noqa: BLE001
                job.attempts += 1
                self._logger.error(
                    "Job failed (key=%s attempt=%s/%s)",
                    job.key,
                    job.attempts,
                    job.max_attempts,
                    exc_info=exc,
                )
                if job.attempts >= job.max_attempts:
                    self._statuses[job.key] = JobStatus.FAILED
                    return
                delay = min(
                    job.backoff_seconds * job.attempts,
                    job.backoff_seconds * job.max_attempts,
                )
                await asyncio.sleep(delay)
            else:
                self._statuses[job.key] = JobStatus.SUCCEEDED
                return
