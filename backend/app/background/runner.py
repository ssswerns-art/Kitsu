import hashlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from ..infrastructure.redis import get_redis

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
        self._logger = logging.getLogger("kitsu.jobs")

    def _make_job_id(self, job: Job) -> str:
        """Generate deterministic job ID from job key."""
        # Use job key as the unique identifier
        return hashlib.sha256(job.key.encode()).hexdigest()[:32]

    def status_for(self, key: str) -> JobStatus | None:
        """Get job status (not implemented for Redis-based runner).
        
        In a distributed environment, job status tracking would require
        additional Redis operations. For now, return None.
        """
        return None

    async def enqueue(self, job: Job) -> Job:
        """Enqueue a job for execution.
        
        Jobs are deduplicated using Redis - if a job with the same key
        is already running, it won't be started again.
        """
        redis = get_redis()
        job_id = self._make_job_id(job)
        
        # Check if job is already running (across all workers)
        is_new = await redis.check_job_running(job_id, ttl_seconds=300)
        
        if not is_new:
            self._logger.info(
                "Job already running, skipping",
                extra={"job_key": job.key, "job_id": job_id}
            )
            return job
        
        # Execute job immediately (no queue needed in this design)
        try:
            await self._run_job(job)
        finally:
            # Mark job as complete
            await redis.mark_job_complete(job_id)
        
        return job

    async def drain(self) -> None:
        """Wait for all jobs to complete.
        
        In Redis-based implementation, this is a no-op since jobs
        are executed immediately when enqueued.
        """
        pass

    async def stop(self) -> None:
        """Stop the job runner.
        
        In Redis-based implementation, this is a no-op since there
        are no background workers to stop.
        """
        pass

    async def _run_job(self, job: Job) -> None:
        """Execute a job with retry logic."""
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
                    return
                # Simple backoff
                import asyncio
                delay = min(
                    job.backoff_seconds * job.attempts,
                    job.backoff_seconds * job.max_attempts,
                )
                await asyncio.sleep(delay)
            else:
                return
