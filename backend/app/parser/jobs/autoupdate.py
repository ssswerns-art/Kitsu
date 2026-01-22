from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import AsyncContextManager, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.infrastructure.redis import get_redis

from ..services.autoupdate_service import (
    ParserEpisodeAutoupdateService,
    resolve_update_interval_minutes,
)
from ..services.sync_service import get_parser_settings


DEFAULT_INTERVAL_MINUTES = 60
SCHEDULER_LOCK_KEY = "parser:autoupdate:scheduler"
SCHEDULER_LOCK_TTL = 120  # 2 minutes (longer than typical interval to prevent overlap)

logger = logging.getLogger(__name__)


class ParserAutoupdateScheduler:
    def __init__(
        self,
        *,
        session_factory: Callable[
            [], AsyncContextManager[AsyncSession]
        ] = AsyncSessionLocal,
        service_factory: Callable[..., ParserEpisodeAutoupdateService] = (
            ParserEpisodeAutoupdateService
        ),
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the scheduler loop.
        
        Multiple workers can call this, but only one will be active at a time
        due to distributed locking.
        """
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def run_once(self, *, force: bool = False) -> dict[str, object]:
        """Run autoupdate once.
        
        In distributed mode, this will skip if another worker is already running.
        Set force=True to bypass the lock (for manual triggers).
        """
        redis = get_redis()
        
        # Try to acquire scheduler lock
        if not force:
            job_id = "parser:autoupdate:once"
            is_new = await redis.check_job_running(job_id, ttl_seconds=300)
            if not is_new:
                logger.info("Autoupdate already running in another worker, skipping")
                return {"status": "skipped", "reason": "already_running"}
        
        try:
            async with self._session_factory() as session:
                settings = await get_parser_settings(session)
                interval = resolve_update_interval_minutes(settings)
                if not settings.enable_autoupdate and not force:
                    return {"status": "disabled", "interval_minutes": interval}
                service = self._service_factory(session=session, settings=settings)
                summary = await service.run(force=True)
                summary["interval_minutes"] = interval
                return summary
        finally:
            if not force:
                await redis.mark_job_complete(job_id)

    async def _loop(self) -> None:
        """Main scheduler loop.
        
        Only one instance across all workers will be active at a time.
        Each iteration tries to acquire a distributed lock.
        """
        # ISSUE #11: Log scheduler first run for observability
        logger.info("Parser autoupdate scheduler loop started")
        first_iteration = True
        
        while True:
            try:
                redis = get_redis()
                
                # Try to acquire scheduler lock
                async with redis.acquire_lock(
                    SCHEDULER_LOCK_KEY,
                    ttl_seconds=SCHEDULER_LOCK_TTL,
                ) as acquired:
                    if acquired:
                        # ISSUE #11: Log first iteration explicitly
                        if first_iteration:
                            logger.info("Scheduler acquired lock on first iteration, running autoupdate")
                            first_iteration = False
                        else:
                            logger.info("Acquired scheduler lock, running autoupdate")
                        
                        result = await self.run_once(force=False)
                        interval = int(result.get("interval_minutes") or DEFAULT_INTERVAL_MINUTES)
                    else:
                        # Another worker has the lock
                        logger.debug("Scheduler lock held by another worker, sleeping")
                        interval = DEFAULT_INTERVAL_MINUTES
                        first_iteration = False  # Not really the first iteration anymore
                
                # Sleep until next cycle
                await asyncio.sleep(interval * 60)
                
            except Exception as exc:
                # ISSUE #11: Log fatal error on first iteration
                if first_iteration:
                    logger.error("Scheduler FATAL ERROR on first iteration - autoupdate will not run", exc_info=exc)
                    first_iteration = False
                else:
                    logger.error("Scheduler loop error", exc_info=exc)
                # Sleep before retrying on error
                await asyncio.sleep(60)


parser_autoupdate_scheduler = ParserAutoupdateScheduler()
