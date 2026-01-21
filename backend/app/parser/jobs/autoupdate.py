from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import suppress
from typing import AsyncContextManager, Callable

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.infra.redis import DistributedLock, GlobalJobCounter, get_async_redis_client

from ..services.autoupdate_service import (
    ParserEpisodeAutoupdateService,
    resolve_update_interval_minutes,
)
from ..services.sync_service import get_parser_settings


DEFAULT_INTERVAL_MINUTES = 60
SCHEDULER_LOCK_KEY = "parser_autoupdate_scheduler"
SCHEDULER_LOCK_TTL = 90  # seconds

# Parser-specific concurrency limit
PARSER_MAX_CONCURRENCY = 5
PARSER_COUNTER_KEY = "parser_jobs"


logger = logging.getLogger("kitsu.parser.autoupdate")


class ParserAutoupdateScheduler:
    """
    Scheduler for parser auto-update that runs EXACTLY ONCE across all workers.
    Uses Redis distributed lock to ensure single-instance execution.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[
            [], AsyncContextManager[AsyncSession]
        ] = AsyncSessionLocal,
        service_factory: Callable[..., ParserEpisodeAutoupdateService] = (
            ParserEpisodeAutoupdateService
        ),
        redis_client: AsyncRedis | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._redis = redis_client
        self._task: asyncio.Task[None] | None = None
        self._lock: DistributedLock | None = None
        self._lock_extend_task: asyncio.Task[None] | None = None
        self._should_stop = False  # Flag for graceful shutdown
        self._worker_id = str(uuid.uuid4())[:8]  # Short UUID for observability

    async def _ensure_redis(self) -> AsyncRedis:
        """Lazy initialize Redis client."""
        if self._redis is None:
            try:
                self._redis = get_async_redis_client()
                await self._redis.ping()
            except (RedisError, ValueError) as exc:
                logger.error("Redis unavailable for scheduler: %s", exc)
                raise
        return self._redis

    async def start(self) -> None:
        """
        Start scheduler if lock can be acquired.
        Only ONE instance across all workers will start.
        """
        if self._task and not self._task.done():
            return

        self._should_stop = False  # Reset stop flag

        try:
            # Try to acquire distributed lock
            redis = await self._ensure_redis()
            self._lock = DistributedLock(
                redis, SCHEDULER_LOCK_KEY, ttl_seconds=SCHEDULER_LOCK_TTL
            )

            logger.info(
                "[SCHEDULER] lock_acquire_attempt lock_key=%s worker_id=%s",
                SCHEDULER_LOCK_KEY,
                self._worker_id,
            )

            if await self._lock.acquire():
                logger.info(
                    "[SCHEDULER] lock_acquired lock_key=%s worker_id=%s ttl=%ds",
                    SCHEDULER_LOCK_KEY,
                    self._worker_id,
                    SCHEDULER_LOCK_TTL,
                )
                self._task = asyncio.create_task(self._loop())
                # Start lock extension task
                self._lock_extend_task = asyncio.create_task(self._extend_lock_loop())
            else:
                logger.info(
                    "[SCHEDULER] lock_denied lock_key=%s reason=held_by_another_worker worker_id=%s",
                    SCHEDULER_LOCK_KEY,
                    self._worker_id,
                )

        except (RedisError, ValueError) as exc:
            logger.error(
                "[SCHEDULER] start_failed lock_key=%s reason=redis_unavailable worker_id=%s error=%s",
                SCHEDULER_LOCK_KEY,
                self._worker_id,
                exc,
            )

    async def stop(self) -> None:
        """Stop scheduler and release lock."""
        # Signal graceful shutdown
        self._should_stop = True

        # Stop lock extension
        if self._lock_extend_task:
            self._lock_extend_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._lock_extend_task
            self._lock_extend_task = None

        # Stop main task
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

        # Release lock
        if self._lock:
            try:
                await self._lock.release()
                logger.info(
                    "[SCHEDULER] stopped lock_key=%s reason=graceful worker_id=%s",
                    SCHEDULER_LOCK_KEY,
                    self._worker_id,
                )
            except (RedisError, ValueError) as exc:
                logger.warning(
                    "[SCHEDULER] stopped lock_key=%s reason=redis_error worker_id=%s error=%s",
                    SCHEDULER_LOCK_KEY,
                    self._worker_id,
                    exc,
                )
            self._lock = None

    async def run_once(self, *, force: bool = False) -> dict[str, object]:
        """Run autoupdate once (for manual triggers or testing)."""
        parser_acquired = False
        try:
            # Check parser concurrency limit
            redis = await self._ensure_redis()
            parser_counter = GlobalJobCounter(redis, PARSER_COUNTER_KEY, PARSER_MAX_CONCURRENCY)
            
            if not await parser_counter.try_acquire():
                logger.error(
                    "[PARSER] rejected reason=parser_limit_exceeded max=%d worker_id=%s",
                    PARSER_MAX_CONCURRENCY,
                    self._worker_id,
                )
                return {
                    "status": "rejected",
                    "reason": "parser_limit_exceeded",
                    "max_concurrency": PARSER_MAX_CONCURRENCY,
                }
            
            parser_acquired = True
            
            async with self._session_factory() as session:
                settings = await get_parser_settings(session)
                interval = resolve_update_interval_minutes(settings)
                if not settings.enable_autoupdate and not force:
                    return {"status": "disabled", "interval_minutes": interval}
                service = self._service_factory(session=session, settings=settings)
                summary = await service.run(force=True)
                summary["interval_minutes"] = interval
                return summary
                
        except (RedisError, ValueError) as exc:
            logger.error(
                "[PARSER] redis_error reason=redis_unavailable worker_id=%s error=%s",
                self._worker_id,
                exc,
            )
            return {
                "status": "failed",
                "reason": "redis_unavailable",
            }
        finally:
            # Always release parser slot
            if parser_acquired:
                try:
                    redis = await self._ensure_redis()
                    parser_counter = GlobalJobCounter(redis, PARSER_COUNTER_KEY, PARSER_MAX_CONCURRENCY)
                    await parser_counter.release()
                except (RedisError, ValueError) as exc:
                    logger.error(
                        "[PARSER] counter_release_failed worker_id=%s error=%s",
                        self._worker_id,
                        exc,
                    )

    async def _extend_lock_loop(self) -> None:
        """Periodically extend lock to prevent expiration."""
        if not self._lock:
            return

        try:
            while not self._should_stop:
                # Extend lock every TTL/2 seconds
                await asyncio.sleep(SCHEDULER_LOCK_TTL / 2)
                if self._should_stop:
                    break
                if not await self._lock.extend():
                    logger.error(
                        "[SCHEDULER] ttl_extend_failed lock_key=%s reason=lock_lost worker_id=%s",
                        SCHEDULER_LOCK_KEY,
                        self._worker_id,
                    )
                    # Signal graceful shutdown instead of canceling
                    self._should_stop = True
                    break
                logger.debug(
                    "[SCHEDULER] ttl_extended lock_key=%s ttl=%ds worker_id=%s",
                    SCHEDULER_LOCK_KEY,
                    SCHEDULER_LOCK_TTL,
                    self._worker_id,
                )
        except asyncio.CancelledError:
            return

    async def _loop(self) -> None:
        """Main scheduler loop."""
        while not self._should_stop:
            result = await self.run_once()
            interval = int(result.get("interval_minutes") or DEFAULT_INTERVAL_MINUTES)
            
            # Sleep in small chunks to allow graceful shutdown
            for _ in range(interval * 60):
                if self._should_stop:
                    break
                await asyncio.sleep(1)


parser_autoupdate_scheduler = ParserAutoupdateScheduler()
