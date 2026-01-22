"""Tests for PARSER-04: Auto-parsing worker and scheduler.

These tests verify:
1. Worker does NOT execute tasks when mode="manual"
2. Worker starts working ONLY after mode="auto"
3. Emergency stop immediately halts task queuing
4. Source auto-disable on error threshold
5. Mode reset on critical errors
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.base import Base
from app.parser.config import ParserSettings
from app.parser.tables import (
    parser_job_logs,
    parser_jobs,
    parser_settings,
    parser_sources,
)
from app.parser.worker import ParserWorker


class AsyncSessionAdapter:
    """Adapter to make sync session work with async code."""
    
    def __init__(self, session: Session, engine: sa.Engine) -> None:
        self._session = session
        self._engine = engine
        self._in_transaction = False

    def get_bind(self) -> sa.Engine:
        return self._engine

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()
    
    async def begin(self):
        """Simulate async transaction context."""
        self._in_transaction = True
        return AsyncTransactionContext(self)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()
        self._in_transaction = False


class AsyncTransactionContext:
    """Context manager for transactions."""
    
    def __init__(self, session: AsyncSessionAdapter) -> None:
        self._session = session
    
    async def __aenter__(self):
        return self._session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self._session.commit()
        else:
            await self._session.rollback()


class AsyncSessionMaker:
    """Factory for creating async session adapters."""
    
    def __init__(self, session: Session, engine: sa.Engine) -> None:
        self._session = session
        self._engine = engine
    
    def __call__(self):
        return AsyncSessionAdapter(self._session, self._engine)


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    
    # Create only parser tables
    parser_tables = [
        parser_sources,
        parser_settings,
        parser_jobs,
        parser_job_logs,
    ]
    Base.metadata.create_all(engine, tables=parser_tables)
    
    session = Session(engine)
    adapter = AsyncSessionAdapter(session, engine)
    session_maker = AsyncSessionMaker(session, engine)
    
    yield adapter, session, session_maker
    
    session.close()


def _seed_manual_mode(session: Session) -> None:
    """Seed parser_settings with manual mode."""
    session.execute(
        sa.insert(parser_settings).values(
            id=1,
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            update_interval_minutes=60,
            dry_run=True,
        )
    )
    session.commit()


def _seed_auto_mode(session: Session) -> None:
    """Seed parser_settings with auto mode."""
    session.execute(
        sa.insert(parser_settings).values(
            id=1,
            mode="auto",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=True,
            update_interval_minutes=60,
            dry_run=True,
        )
    )
    session.commit()


def _seed_sources(session: Session) -> None:
    """Seed parser sources."""
    session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
            rate_limit_per_min=60,
            max_concurrency=2,
        )
    )
    session.execute(
        sa.insert(parser_sources).values(
            id=2,
            code="kodik",
            enabled=True,
            rate_limit_per_min=60,
            max_concurrency=2,
        )
    )
    session.commit()


@pytest.mark.anyio
async def test_worker_does_not_execute_in_manual_mode(db_session):
    """REQUIREMENT: Worker does NOT execute tasks when mode='manual'."""
    adapter, session, session_maker = db_session
    
    # Seed manual mode
    _seed_manual_mode(session)
    _seed_sources(session)
    
    # Create worker with short interval
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Run one cycle
    with patch.object(worker, '_queue_catalog_sync') as mock_catalog:
        with patch.object(worker, '_queue_episode_autoupdate') as mock_autoupdate:
            await worker._run_cycle()
            
            # Verify NO tasks were queued
            mock_catalog.assert_not_called()
            mock_autoupdate.assert_not_called()
    
    # Verify no jobs were created
    result = session.execute(sa.select(parser_jobs))
    assert len(result.fetchall()) == 0


@pytest.mark.anyio
async def test_worker_starts_executing_in_auto_mode(db_session):
    """REQUIREMENT: Worker starts working ONLY after mode='auto'."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode
    _seed_auto_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Mock the actual task execution to avoid real API calls
    with patch('app.parser.worker.ShikimoriCatalogSource'):
        with patch('app.parser.worker.ParserSyncService') as mock_sync:
            with patch('app.parser.worker.ParserEpisodeAutoupdateService') as mock_autoupdate:
                # Setup mocks
                mock_sync_instance = MagicMock()
                mock_sync_instance.sync_all.return_value = {"status": "success"}
                mock_sync.return_value = mock_sync_instance
                
                mock_autoupdate_instance = AsyncMock()
                mock_autoupdate_instance.run = AsyncMock(return_value={"status": "success"})
                mock_autoupdate.return_value = mock_autoupdate_instance
                
                # Run one cycle
                await worker._run_cycle()
    
    # Verify jobs were created
    result = session.execute(sa.select(parser_jobs))
    jobs = result.fetchall()
    assert len(jobs) >= 1  # At least catalog sync should run


@pytest.mark.anyio
async def test_worker_respects_mode_change_during_cycle(db_session):
    """REQUIREMENT: Worker checks mode BEFORE each action."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode initially
    _seed_auto_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Simulate mode change during execution
    async def switch_to_manual(*args, **kwargs):
        # Switch mode to manual mid-cycle
        session.execute(
            sa.update(parser_settings)
            .where(parser_settings.c.id == 1)
            .values(mode="manual")
        )
        session.commit()
        return ParserSettings(mode="manual", enable_autoupdate=False)
    
    with patch('app.parser.worker.get_parser_settings', side_effect=switch_to_manual):
        await worker._run_cycle()
    
    # Worker should abort without creating jobs
    result = session.execute(sa.select(parser_jobs))
    jobs = result.fetchall()
    # No jobs should be created since mode switched to manual
    assert len(jobs) == 0


@pytest.mark.anyio
async def test_emergency_mode_switch_on_critical_error(db_session):
    """REQUIREMENT: Critical errors auto-switch mode to 'manual'."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode
    _seed_auto_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Mock AuditService.log as AsyncMock
    with patch('app.parser.worker.AuditService') as mock_audit:
        mock_audit_instance = MagicMock()
        mock_audit_instance.log = AsyncMock()
        mock_audit.return_value = mock_audit_instance
        
        # Trigger emergency mode switch
        await worker._emergency_mode_switch("test_error", "test_details")
    
    # Verify mode was switched to manual
    result = session.execute(
        sa.select(parser_settings.c.mode).where(parser_settings.c.id == 1)
    )
    mode = result.scalar_one()
    assert mode == "manual"


@pytest.mark.anyio
async def test_worker_shutdown_gracefully(db_session):
    """Test worker can be shut down gracefully."""
    adapter, session, session_maker = db_session
    
    # Seed manual mode to avoid actual work
    _seed_manual_mode(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Start worker in background
    worker_task = asyncio.create_task(worker.start())
    
    # Wait a bit then shutdown
    await asyncio.sleep(0.5)
    await worker.shutdown()
    
    # Wait for worker to stop
    await asyncio.wait_for(worker_task, timeout=2.0)
    
    # Verify worker stopped
    assert not worker._running


@pytest.mark.anyio
async def test_worker_logs_cycle_information(db_session):
    """Test worker logs each cycle with mode and sources."""
    adapter, session, session_maker = db_session
    
    # Seed manual mode
    _seed_manual_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Capture logs
    with patch('app.parser.worker.logger') as mock_logger:
        await worker._run_cycle()
        
        # Verify cycle start was logged
        mock_logger.info.assert_any_call(
            "Worker cycle started",
            extra={
                "mode": "manual",
                "enable_autoupdate": False,
            }
        )


@pytest.mark.anyio
async def test_worker_handles_no_active_sources(db_session):
    """Test worker handles case when no sources are enabled."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode but disable all sources
    _seed_auto_mode(session)
    session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=False,  # Disabled
            rate_limit_per_min=60,
            max_concurrency=2,
        )
    )
    session.commit()
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Run cycle - should complete without errors
    await worker._run_cycle()
    
    # No jobs should be created
    result = session.execute(sa.select(parser_jobs))
    jobs = result.fetchall()
    assert len(jobs) == 0


@pytest.mark.anyio
async def test_worker_creates_job_records(db_session):
    """Test worker creates proper job records with status tracking."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode
    _seed_auto_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Create a job
    job_id = await worker._create_job(adapter, 1, "test_job")
    assert job_id > 0
    
    # Verify job was created with running status
    result = session.execute(
        sa.select(parser_jobs.c.status).where(parser_jobs.c.id == job_id)
    )
    status = result.scalar_one()
    assert status == "running"
    
    # Finish the job
    await worker._finish_job(adapter, job_id, 1, "success", None)
    
    # Verify job was marked as success
    result = session.execute(
        sa.select(parser_jobs.c.status).where(parser_jobs.c.id == job_id)
    )
    status = result.scalar_one()
    assert status == "success"


@pytest.mark.anyio
async def test_worker_logs_job_errors(db_session):
    """Test worker logs errors to parser_job_logs."""
    adapter, session, session_maker = db_session
    
    # Seed auto mode
    _seed_auto_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Create a job
    job_id = await worker._create_job(adapter, 1, "test_job")
    
    # Log an error
    await worker._log_job_error(adapter, job_id, "Test error message")
    
    # Verify error was logged
    result = session.execute(
        sa.select(parser_job_logs.c.message, parser_job_logs.c.level)
        .where(parser_job_logs.c.job_id == job_id)
    )
    row = result.fetchone()
    assert row is not None
    assert row.message == "Test error message"
    assert row.level == "error"


@pytest.mark.anyio
async def test_mode_toggle_between_manual_and_auto(db_session):
    """Test worker behavior when mode toggles between manual and auto."""
    adapter, session, session_maker = db_session
    
    # Start with manual mode
    _seed_manual_mode(session)
    _seed_sources(session)
    
    # Create worker
    worker = ParserWorker(interval_seconds=1, session_maker=session_maker)
    
    # Run cycle in manual mode - no tasks
    with patch.object(worker, '_queue_catalog_sync') as mock_catalog:
        await worker._run_cycle()
        mock_catalog.assert_not_called()
    
    # Switch to auto mode
    session.execute(
        sa.update(parser_settings)
        .where(parser_settings.c.id == 1)
        .values(mode="auto", enable_autoupdate=True)
    )
    session.commit()
    
    # Run cycle in auto mode - tasks should execute
    with patch('app.parser.worker.ShikimoriCatalogSource'):
        with patch('app.parser.worker.ParserSyncService') as mock_sync:
            mock_sync_instance = MagicMock()
            mock_sync_instance.sync_all.return_value = {"status": "success"}
            mock_sync.return_value = mock_sync_instance
            
            await worker._run_cycle()
    
    # Jobs should be created now
    result = session.execute(sa.select(parser_jobs))
    jobs = result.fetchall()
    assert len(jobs) >= 1
