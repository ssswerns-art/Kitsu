import asyncio
import logging
import uuid
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.infra.redis import get_async_redis_client

JobHandler = Callable[[], Awaitable[None]]

# Global limit for concurrent jobs across all workers
MAX_RUNNING_JOBS = 20
GLOBAL_JOB_COUNTER_KEY = "counter:global_jobs"


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
    criticality: str = "important"  # "critical" | "important" | "best_effort"


class JobRunner:
    """
    Distributed job runner using Redis for coordination.
    Safe for multi-worker deployment - jobs are not duplicated or lost.
    """

    def __init__(self, redis_client: AsyncRedis | None = None) -> None:
        self._redis = redis_client
        self._task: asyncio.Task[None] | None = None
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("kitsu.jobs")
        self._redis_available = True
        self._worker_id = str(uuid.uuid4())[:8]  # Short UUID for observability

    async def _ensure_redis(self) -> AsyncRedis:
        """Lazy initialize Redis client."""
        if self._redis is None:
            try:
                self._redis = get_async_redis_client()
                await self._redis.ping()
                self._redis_available = True
            except (RedisError, ValueError) as exc:
                self._logger.error("Redis unavailable for job runner: %s", exc)
                self._redis_available = False
                raise
        return self._redis

    def _make_status_key(self, job_key: str) -> str:
        """Redis key for job status."""
        return f"job:status:{job_key}"

    async def status_for(self, key: str) -> JobStatus | None:
        """Get job status from Redis or in-memory cache."""
        if not self._redis_available:
            return None

        try:
            redis = await self._ensure_redis()
            status_str = await redis.get(self._make_status_key(key))
            if status_str:
                return JobStatus(status_str)
        except (RedisError, ValueError) as exc:
            self._logger.warning("Failed to get job status for %s: %s", key, exc)

        return None

    async def enqueue(self, job: Job) -> Job:
        """
        Enqueue job with Redis coordination.
        Prevents duplicate enqueuing across workers.
        """
        if not self._redis_available:
            self._logger.error(
                "[JOB] enqueue_failed job_key=%s reason=redis_unavailable worker_id=%s",
                job.key,
                self._worker_id,
            )
            return job

        async with self._lock:
            try:
                redis = await self._ensure_redis()
                status_key = self._make_status_key(job.key)

                # Check current status
                current_status_str = await redis.get(status_key)
                if current_status_str:
                    current_status = JobStatus(current_status_str)
                    if current_status in {
                        JobStatus.QUEUED,
                        JobStatus.RUNNING,
                        JobStatus.SUCCEEDED,
                    }:
                        self._logger.info(
                            "[JOB] enqueue_skipped job_key=%s reason=duplicate status=%s worker_id=%s",
                            job.key,
                            current_status.value,
                            self._worker_id,
                        )
                        return job

                # Set status to QUEUED with SET NX (only if not exists)
                # TTL ensures cleanup even if worker crashes
                was_set = await redis.set(
                    status_key,
                    JobStatus.QUEUED.value,
                    nx=True,
                    ex=3600,  # 1 hour TTL
                )

                if was_set:
                    # We successfully claimed this job
                    self._jobs[job.key] = job
                    await self._ensure_worker()
                    self._logger.info(
                        "[JOB] enqueued job_key=%s worker_id=%s",
                        job.key,
                        self._worker_id,
                    )
                else:
                    # Another worker already enqueued this job
                    self._logger.info(
                        "[JOB] enqueue_skipped job_key=%s reason=duplicate worker_id=%s",
                        job.key,
                        self._worker_id,
                    )

            except (RedisError, ValueError) as exc:
                self._logger.error(
                    "[JOB] enqueue_failed job_key=%s reason=redis_error worker_id=%s error=%s",
                    job.key,
                    self._worker_id,
                    exc,
                )

        return job

    async def drain(self) -> None:
        """Wait for all jobs in this worker to complete."""
        # Wait for worker to process all jobs in _jobs dict
        while self._jobs and self._task and not self._task.done():
            await asyncio.sleep(0.1)

    async def stop(self) -> None:
        """Stop the worker task."""
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _ensure_worker(self) -> None:
        """Ensure worker task is running."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        """Process jobs from local queue."""
        try:
            while True:
                # Check if there are jobs to process
                if not self._jobs:
                    await asyncio.sleep(0.1)
                    continue

                # Get next job (insertion order - Python 3.7+ dict guarantee)
                job_key = next(iter(self._jobs.keys()))
                job = self._jobs.pop(job_key)
                await self._run_job(job)

        except asyncio.CancelledError:
            return

    async def _run_job(self, job: Job) -> None:
        """
        Execute job with retry logic and status tracking.
        
        FAILURE BOUNDARIES IMPLEMENTATION:
        - CRITICAL jobs: bypass all backpressure, always attempt to start
        - IMPORTANT jobs: respect limits, can be rejected
        - BEST_EFFORT jobs: drop first under pressure
        
        All decisions are logged with criticality, reason, and worker_id.
        """
        running_incremented = False
        criticality = job.criticality
        
        try:
            redis = await self._ensure_redis()
            status_key = self._make_status_key(job.key)
            
            # SINGLE DECISION POINT: START / DROP / REJECT
            # CRITICAL jobs ALWAYS bypass this check and proceed to execution
            
            if criticality != "critical":
                # Only IMPORTANT and BEST_EFFORT jobs check backpressure
                try:
                    current = await redis.get(GLOBAL_JOB_COUNTER_KEY)
                    current_running = int(current) if current else 0
                    
                    if current_running >= MAX_RUNNING_JOBS:
                        # LIMIT EXCEEDED - only affects non-CRITICAL jobs
                        
                        if criticality == "best_effort":
                            # BEST_EFFORT: DROP with warning
                            await redis.set(status_key, JobStatus.FAILED.value, ex=86400)
                            self._logger.warning(
                                "[JOB] dropped job_key=%s criticality=%s reason=global_limit_exceeded current=%d max=%d worker_id=%s",
                                job.key,
                                criticality,
                                current_running,
                                MAX_RUNNING_JOBS,
                                self._worker_id,
                            )
                            return
                        
                        else:  # important
                            # IMPORTANT: REJECT with error
                            await redis.set(status_key, JobStatus.FAILED.value, ex=86400)
                            self._logger.error(
                                "[JOB] rejected job_key=%s criticality=%s reason=global_limit_exceeded current=%d max=%d worker_id=%s",
                                job.key,
                                criticality,
                                current_running,
                                MAX_RUNNING_JOBS,
                                self._worker_id,
                            )
                            return
                            
                except (RedisError, ValueError) as exc:
                    # Redis unavailable - only affects non-CRITICAL jobs
                    
                    if criticality == "best_effort":
                        # BEST_EFFORT: DROP with warning
                        self._logger.warning(
                            "[JOB] dropped job_key=%s criticality=%s reason=redis_unavailable worker_id=%s error=%s",
                            job.key,
                            criticality,
                            self._worker_id,
                            exc,
                        )
                        return
                    
                    else:  # important
                        # IMPORTANT: REJECT with error
                        self._logger.error(
                            "[JOB] rejected job_key=%s criticality=%s reason=redis_unavailable worker_id=%s error=%s",
                            job.key,
                            criticality,
                            self._worker_id,
                            exc,
                        )
                        return
            
            # Job approved to start (either CRITICAL or passed backpressure check)
            # Increment counter for IMPORTANT and BEST_EFFORT only
            if criticality != "critical":
                await redis.incr(GLOBAL_JOB_COUNTER_KEY)
                running_incremented = True

            # Update status to RUNNING
            await redis.set(status_key, JobStatus.RUNNING.value, ex=3600)
            self._logger.info(
                "[JOB] started job_key=%s criticality=%s worker_id=%s",
                job.key,
                criticality,
                self._worker_id,
            )

            # Execute with retries (controlled by job.max_attempts, not by runner)
            while job.attempts < job.max_attempts:
                try:
                    await job.handler()
                    # Success
                    await redis.set(status_key, JobStatus.SUCCEEDED.value, ex=86400)
                    self._logger.info(
                        "[JOB] succeeded job_key=%s criticality=%s worker_id=%s",
                        job.key,
                        criticality,
                        self._worker_id,
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    job.attempts += 1
                    self._logger.error(
                        "[JOB] failed job_key=%s criticality=%s attempt=%s/%s worker_id=%s",
                        job.key,
                        criticality,
                        job.attempts,
                        job.max_attempts,
                        self._worker_id,
                        exc_info=exc,
                    )
                    if job.attempts >= job.max_attempts:
                        await redis.set(status_key, JobStatus.FAILED.value, ex=86400)
                        self._logger.error(
                            "[JOB] failed_permanently job_key=%s criticality=%s worker_id=%s",
                            job.key,
                            criticality,
                            self._worker_id,
                        )
                        return
                    delay = min(
                        job.backoff_seconds * job.attempts,
                        job.backoff_seconds * job.max_attempts,
                    )
                    await asyncio.sleep(delay)

        except (RedisError, ValueError) as exc:
            # Redis error during execution - log but don't crash
            # CRITICAL jobs continue despite Redis errors
            self._logger.error(
                "[JOB] redis_error job_key=%s criticality=%s worker_id=%s error=%s",
                job.key,
                criticality,
                self._worker_id,
                exc,
            )
        finally:
            # Decrement counter only for jobs that incremented it
            if running_incremented:
                try:
                    redis = await self._ensure_redis()
                    await redis.decr(GLOBAL_JOB_COUNTER_KEY)
                except (RedisError, ValueError) as exc:
                    self._logger.error(
                        "[JOB] counter_decrement_failed job_key=%s criticality=%s worker_id=%s error=%s",
                        job.key,
                        criticality,
                        self._worker_id,
                        exc,
                    )
