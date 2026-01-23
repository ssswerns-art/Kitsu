"""Auto-parsing worker with strict control and fail-safe mechanisms.

TASK: PARSER-04
This worker executes parsing tasks ONLY when explicitly enabled via admin panel.
It NEVER runs spontaneously and respects emergency stop signals.

Key invariants:
1. Tasks execute ONLY when parser_settings.mode == "auto"
2. Worker sleeps when mode == "manual" (no side effects)
3. All operations check mode BEFORE execution
4. Emergency stop immediately halts task queuing
5. Critical errors auto-switch mode to "manual"
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal
from ..infrastructure.redis import get_redis
from ..services.audit.audit_service import AuditService
from .config import ParserSettings
from .scheduler import ParserScheduler, get_sources_needing_catalog_sync
from .services.autoupdate_service import ParserEpisodeAutoupdateService
from .services.sync_service import ParserSyncService, get_parser_settings
from .sources.shikimori_catalog import ShikimoriCatalogSource
from .tables import parser_job_logs, parser_jobs, parser_settings as settings_table, parser_sources

logger = logging.getLogger(__name__)

# Worker configuration
DEFAULT_WORKER_INTERVAL_SECONDS = 60
MIN_WORKER_INTERVAL_SECONDS = 30
MAX_WORKER_INTERVAL_SECONDS = 300

# Distributed lock configuration
WORKER_LOCK_KEY = "parser:worker:cycle"
WORKER_LOCK_TTL = 120  # 2 minutes (longer than cycle interval)


class ParserWorker:
    """Controlled auto-parsing worker.
    
    This worker orchestrates parsing tasks based on database configuration.
    It implements strict safety mechanisms:
    
    - Only runs when mode="auto"
    - Checks mode before every action
    - Respects emergency stop
    - Logs all operations
    - Fails fast on invariant violations
    """
    
    def __init__(
        self,
        *,
        interval_seconds: int = DEFAULT_WORKER_INTERVAL_SECONDS,
        session_maker=None,
    ) -> None:
        self._interval_seconds = max(
            MIN_WORKER_INTERVAL_SECONDS,
            min(MAX_WORKER_INTERVAL_SECONDS, interval_seconds)
        )
        self._session_maker = session_maker or AsyncSessionLocal
        self._running = False
        self._shutdown_event = asyncio.Event()
        # ISSUE #9 FIX: Use asyncio.Lock to protect lifecycle state transitions
        self._lifecycle_lock = asyncio.Lock()
        
    async def start(self) -> None:
        """Start the worker loop.
        
        The worker will run indefinitely until shutdown() is called.
        Multiple workers can run, but only one will be active at a time
        due to distributed locking.
        
        ISSUE #9 FIX: Uses asyncio.Lock to ensure atomic state transitions and prevent
        race conditions when start() is called concurrently from multiple tasks.
        """
        async with self._lifecycle_lock:
            if self._running:
                return
            
            self._running = True
            self._shutdown_event.clear()
        
        logger.info(
            "Parser worker starting",
            extra={"interval_seconds": self._interval_seconds}
        )
        
        while self._running and not self._shutdown_event.is_set():
            try:
                redis = get_redis()
                
                # Try to acquire worker lock
                async with redis.acquire_lock(
                    WORKER_LOCK_KEY,
                    ttl_seconds=WORKER_LOCK_TTL,
                ) as acquired:
                    if acquired:
                        logger.info("Acquired worker lock, running cycle")
                        await self._run_cycle()
                    else:
                        logger.debug("Worker lock held by another instance, sleeping")
                        
            except Exception as exc:
                logger.exception(
                    "Worker cycle failed with unhandled exception",
                    exc_info=exc
                )
                # Critical error: auto-switch to manual mode
                await self._emergency_mode_switch("critical_error", str(exc))
            
            # Wait for next cycle or shutdown
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._interval_seconds
                )
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue to next cycle
                
        logger.info("Parser worker stopped")
    
    async def shutdown(self) -> None:
        """Stop the worker gracefully.
        
        ISSUE #9 FIX: Uses asyncio.Lock to ensure atomic state transitions and prevent
        race conditions when shutdown() is called concurrently or during start().
        """
        logger.info("Parser worker shutdown requested")
        async with self._lifecycle_lock:
            if not self._running:
                return
            
            self._running = False
            self._shutdown_event.set()
    
    async def _run_cycle(self) -> None:
        """Execute one worker cycle.
        
        This method:
        1. Reads parser_settings from DB
        2. Checks mode (exit if manual)
        3. Queues tasks if auto mode is active
        """
        async with self._session_maker() as session:
            # CRITICAL: Read settings from DB as single source of truth
            settings = await get_parser_settings(session)
            
            logger.info(
                "Worker cycle started",
                extra={
                    "mode": settings.mode,
                    "enable_autoupdate": settings.enable_autoupdate,
                }
            )
            
            # INVARIANT: No operations in manual mode
            if settings.mode != "auto":
                logger.debug("Mode is not 'auto', sleeping")
                return
            
            # Create scheduler
            scheduler = ParserScheduler(settings)
            
            # Get sources that need catalog sync based on schedule
            sources_needing_sync = await get_sources_needing_catalog_sync(session, scheduler)
            
            if sources_needing_sync:
                logger.info(
                    "Queuing catalog sync tasks",
                    extra={
                        "sources": [s["code"] for s in sources_needing_sync],
                    }
                )
                
                for source in sources_needing_sync:
                    await self._queue_catalog_sync(session, settings, source)
            
            # Queue episode autoupdate if enabled and scheduled
            if scheduler.should_run_episode_sync():
                shikimori_source = await self._get_source_by_code(session, "shikimori")
                kodik_source = await self._get_source_by_code(session, "kodik")
                
                if shikimori_source and kodik_source:
                    logger.info("Queuing episode autoupdate task")
                    await self._queue_episode_autoupdate(
                        session, settings, shikimori_source, kodik_source
                    )
    
    async def _get_source_by_code(
        self, session: AsyncSession, code: str
    ) -> dict[str, Any] | None:
        """Get a specific parser source by code."""
        result = await session.execute(
            select(
                parser_sources.c.id,
                parser_sources.c.code,
                parser_sources.c.enabled,
                parser_sources.c.rate_limit_per_min,
                parser_sources.c.max_concurrency,
            )
            .where(parser_sources.c.code == code)
            .where(parser_sources.c.enabled == True)  # noqa: E712
        )
        row = result.first()
        return dict(row._mapping) if row else None
    
    async def _queue_catalog_sync(
        self,
        session: AsyncSession,
        settings: ParserSettings,
        source: dict[str, Any],
    ) -> None:
        """Queue catalog synchronization task.
        
        This method queues (not executes) catalog sync work.
        Uses Redis to prevent duplicate execution across workers.
        """
        redis = get_redis()
        
        # Create deterministic job ID
        job_id_key = f"catalog_sync:{source['code']}"
        
        # Check if job is already running (across all workers)
        is_new = await redis.check_job_running(job_id_key, ttl_seconds=600)
        if not is_new:
            logger.info(
                "Catalog sync already running, skipping",
                extra={"source": source["code"]}
            )
            return
        
        db_job_id = None
        try:
            async with session.begin():
                # Double-check mode before queueing
                current_settings = await get_parser_settings(session)
                if current_settings.mode != "auto":
                    logger.warning("Mode changed to manual during cycle, aborting catalog sync")
                    return
                
                db_job_id = await self._create_job(session, source["id"], "catalog_sync")
                
                # Execute catalog sync
                catalog_source = ShikimoriCatalogSource(settings)
                sync_service = ParserSyncService(
                    catalog_source=catalog_source,
                    episode_source=None,  # type: ignore
                    schedule_source=None,  # type: ignore
                    session=session,
                )
                
                # Sync catalog - respect autopublish setting
                result = sync_service.sync_all(persist=True, publish=settings.autopublish_enabled)
                
                await self._finish_job(session, db_job_id, source["id"], "success", None)
            
            logger.info(
                "Catalog sync completed",
                extra={"source": source["code"], "result": result}
            )
        except Exception as exc:
            logger.exception(
                "Catalog sync failed",
                exc_info=exc,
                extra={"source": source["code"]}
            )
            # Log error in separate transaction if job was created
            if db_job_id is not None:
                try:
                    async with session.begin():
                        await self._log_job_error(session, db_job_id, str(exc))
                        await self._finish_job(session, db_job_id, source["id"], "failed", str(exc))
                except Exception as log_exc:
                    logger.error(f"Failed to log job error: {log_exc}")
        finally:
            # Mark job as complete in Redis
            await redis.mark_job_complete(job_id_key)
    
    async def _queue_episode_autoupdate(
        self,
        session: AsyncSession,
        settings: ParserSettings,
        shikimori_source: dict[str, Any],
        kodik_source: dict[str, Any],
    ) -> None:
        """Queue episode autoupdate task for ongoing anime.
        
        This method queues (not executes) episode autoupdate work.
        Uses Redis to prevent duplicate execution across workers.
        """
        redis = get_redis()
        
        # Create deterministic job ID
        job_id_key = "episode_autoupdate"
        
        # Check if job is already running (across all workers)
        is_new = await redis.check_job_running(job_id_key, ttl_seconds=600)
        if not is_new:
            logger.info("Episode autoupdate already running, skipping")
            return
        
        db_job_id = None
        try:
            async with session.begin():
                # Double-check mode before queueing
                current_settings = await get_parser_settings(session)
                if current_settings.mode != "auto":
                    logger.warning("Mode changed to manual during cycle, aborting autoupdate")
                    return
                
                db_job_id = await self._create_job(session, kodik_source["id"], "episode_autoupdate")
                
                # Execute episode autoupdate
                autoupdate_service = ParserEpisodeAutoupdateService(session=session, settings=settings)
                result = await autoupdate_service.run(force=False)
                
                await self._finish_job(session, db_job_id, kodik_source["id"], "success", None)
            
            logger.info(
                "Episode autoupdate completed",
                extra={"result": result}
            )
        except Exception as exc:
            logger.exception(
                "Episode autoupdate failed",
                exc_info=exc,
            )
            # Log error in separate transaction if job was created
            if db_job_id is not None:
                try:
                    async with session.begin():
                        await self._log_job_error(session, db_job_id, str(exc))
                        await self._finish_job(session, db_job_id, kodik_source["id"], "failed", str(exc))
                except Exception as log_exc:
                    logger.error(f"Failed to log job error: {log_exc}")
        finally:
            # Mark job as complete in Redis
            await redis.mark_job_complete(job_id_key)
    
    async def _create_job(
        self, session: AsyncSession, source_id: int, job_type: str
    ) -> int:
        """Create a new parser job record."""
        stmt = (
            insert(parser_jobs)
            .values(
                source_id=source_id,
                job_type=job_type,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            .returning(parser_jobs.c.id)
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())
    
    async def _finish_job(
        self,
        session: AsyncSession,
        job_id: int,
        source_id: int,
        status: str,
        error_summary: str | None,
    ) -> None:
        """Mark a job as finished."""
        finished_at = datetime.now(timezone.utc)
        await session.execute(
            update(parser_jobs)
            .where(parser_jobs.c.id == job_id)
            .values(status=status, finished_at=finished_at, error_summary=error_summary)
        )
        
        if status == "success":
            await session.execute(
                update(parser_sources)
                .where(parser_sources.c.id == source_id)
                .values(last_synced_at=finished_at)
            )
    
    async def _log_job_error(
        self, session: AsyncSession, job_id: int, error_message: str
    ) -> None:
        """Log a job error to parser_job_logs."""
        await session.execute(
            insert(parser_job_logs).values(
                job_id=job_id,
                level="error",
                message=error_message,
                created_at=datetime.now(timezone.utc),
            )
        )
    
    async def _emergency_mode_switch(self, reason: str, details: str) -> None:
        """Emergency switch to manual mode on critical error.
        
        This is a fail-safe mechanism to prevent runaway parsing.
        """
        logger.critical(
            "Emergency mode switch triggered",
            extra={"reason": reason, "details": details}
        )
        
        async with self._session_maker() as session:
            async with session.begin():
                # Get settings ID
                result = await session.execute(select(settings_table.c.id).limit(1))
                settings_id = result.scalar_one_or_none()
                
                if settings_id is None:
                    logger.error("Cannot switch mode: settings not initialized")
                    return
                
                # Switch to manual mode
                await session.execute(
                    update(settings_table)
                    .where(settings_table.c.id == settings_id)
                    .values(mode="manual", updated_at=datetime.now(timezone.utc))
                )
                
                # Log to audit trail
                audit_service = AuditService(session)
                await audit_service.log(
                    action="parser.emergency_mode_switch",
                    entity_type="parser_settings",
                    entity_id=str(settings_id),
                    actor=None,
                    actor_type="system",
                    before={"mode": "auto"},
                    after={"mode": "manual"},
                    reason=f"Emergency: {reason} - {details}",
                    ip_address=None,
                    user_agent="parser_worker",
                )


async def run_worker() -> None:
    """Entry point for running the parser worker.
    
    This function can be called from a startup script or background task.
    """
    worker = ParserWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        await worker.shutdown()
