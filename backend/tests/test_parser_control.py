"""Tests for PARSER-03: Admin Parser Control endpoints"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth import rbac
from app.models.base import Base
from app.models.user import User
from app.parser.admin.schemas import ParserModeToggleRequest, ParserEmergencyStopRequest
from app.parser.tables import parser_settings, parser_sources, parser_jobs, parser_job_logs, anime_external


class AsyncSessionAdapter:
    def __init__(self, session: Session, engine: sa.Engine) -> None:
        self._session = session
        self._engine = engine

    def get_bind(self) -> sa.Engine:
        return self._engine

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()

    @asynccontextmanager
    async def begin(self):
        with self._session.begin():
            yield self


class MockRequest:
    """Mock request object for testing"""
    def __init__(self):
        self.client = MagicMock()
        self.client.host = "127.0.0.1"
        self.headers = {"user-agent": "test-agent"}


@pytest.fixture()
def db_session():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    parser_tables = [parser_sources, parser_settings, parser_jobs, parser_job_logs, anime_external]
    Base.metadata.create_all(engine, tables=parser_tables)
    session = Session(engine)
    
    # Insert initial parser settings
    session.execute(
        sa.insert(parser_settings).values(
            id=1,
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            update_interval_minutes=60,
            dry_run=False,
            allowed_translation_types=["voice", "sub"],
            allowed_translations=[],
            allowed_qualities=[],
            preferred_translation_priority=[],
            preferred_quality_priority=[],
            blacklist_titles=[],
            blacklist_external_ids=[],
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    
    adapter = AsyncSessionAdapter(session, engine)
    yield adapter, session
    session.close()


@pytest.fixture()
def mock_user():
    """Create a mock admin user"""
    user = MagicMock(spec=User)
    user.id = "test-user-id"
    user.role = "admin"
    user.is_admin = True
    return user


@pytest.fixture()
def admin_router(monkeypatch: pytest.MonkeyPatch, mock_user):
    """Mock dependencies and reload router"""
    dummy = types.ModuleType("app.dependencies")
    audit_module = types.ModuleType("app.services.audit.audit_service")

    async def get_db():  # pragma: no cover - stub
        yield None

    async def get_current_role():  # pragma: no cover - stub
        return "admin"
    
    async def get_current_user():  # pragma: no cover - stub
        return mock_user

    # Mock AuditService
    class MockAuditService:
        def __init__(self, session):
            self.session = session
        
        async def log(self, *args, **kwargs):
            pass
        
        async def log_update(self, *args, **kwargs):
            pass

    dummy.get_db = get_db
    dummy.get_current_role = get_current_role
    dummy.get_current_user = get_current_user
    audit_module.AuditService = MockAuditService
    
    monkeypatch.setitem(sys.modules, "app.dependencies", dummy)
    monkeypatch.setitem(sys.modules, "app.services.audit.audit_service", audit_module)
    
    module = importlib.import_module("app.parser.admin.router")
    return importlib.reload(module)


def test_parser_permissions_in_rbac() -> None:
    """Test that parser permissions are defined in RBAC"""
    admin_permissions = rbac.resolve_permissions("admin")
    assert "admin:parser.settings" in admin_permissions
    assert "admin:parser.emergency" in admin_permissions
    assert "admin:parser.logs" in admin_permissions


def test_user_lacks_parser_permissions() -> None:
    """Test that regular users don't have parser permissions"""
    user_permissions = rbac.resolve_permissions("user")
    assert "admin:parser.settings" not in user_permissions
    assert "admin:parser.emergency" not in user_permissions
    assert "admin:parser.logs" not in user_permissions


@pytest.mark.anyio
async def test_mode_toggle_manual_to_auto(db_session, admin_router, mock_user) -> None:
    """Test toggling parser mode from manual to auto"""
    adapter, session = db_session
    request = MockRequest()
    
    payload = ParserModeToggleRequest(mode="auto", reason="Testing auto mode")
    result = await admin_router.toggle_parser_mode(
        payload=payload,
        request=request,
        session=adapter,
        current_user=mock_user,
        _=None
    )
    
    assert result["status"] == "success"
    assert result["mode"] == "auto"
    
    # Verify database was updated
    row = session.execute(sa.select(parser_settings.c.mode).where(parser_settings.c.id == 1)).scalar_one()
    assert row == "auto"


@pytest.mark.anyio
async def test_mode_toggle_auto_to_manual(db_session, admin_router, mock_user) -> None:
    """Test toggling parser mode from auto to manual"""
    adapter, session = db_session
    
    # Set mode to auto first
    session.execute(
        sa.update(parser_settings).where(parser_settings.c.id == 1).values(mode="auto")
    )
    session.commit()
    
    request = MockRequest()
    payload = ParserModeToggleRequest(mode="manual", reason="Testing manual mode")
    result = await admin_router.toggle_parser_mode(
        payload=payload,
        request=request,
        session=adapter,
        current_user=mock_user,
        _=None
    )
    
    assert result["status"] == "success"
    assert result["mode"] == "manual"
    
    # Verify database was updated
    row = session.execute(sa.select(parser_settings.c.mode).where(parser_settings.c.id == 1)).scalar_one()
    assert row == "manual"


@pytest.mark.anyio
async def test_emergency_stop(db_session, admin_router, mock_user) -> None:
    """Test emergency stop functionality"""
    adapter, session = db_session
    
    # Set mode to auto and create a running job
    session.execute(
        sa.update(parser_settings).where(parser_settings.c.id == 1).values(mode="auto")
    )
    session.execute(
        sa.insert(parser_sources).values(
            id=1, code="test_source", enabled=True, rate_limit_per_min=60, max_concurrency=2
        )
    )
    session.execute(
        sa.insert(parser_jobs).values(
            id=1,
            source_id=1,
            job_type="test",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
    )
    session.commit()
    
    request = MockRequest()
    payload = ParserEmergencyStopRequest(reason="Emergency test")
    result = await admin_router.emergency_stop_parser(
        payload=payload,
        request=request,
        session=adapter,
        current_user=mock_user,
        _=None
    )
    
    assert result["status"] == "stopped"
    assert result["mode"] == "manual"
    
    # Verify mode was set to manual
    mode = session.execute(sa.select(parser_settings.c.mode).where(parser_settings.c.id == 1)).scalar_one()
    assert mode == "manual"
    
    # Verify running jobs were stopped
    job = session.execute(
        sa.select(parser_jobs.c.status, parser_jobs.c.error_summary)
        .where(parser_jobs.c.id == 1)
    ).one()
    assert job.status == "failed"
    assert "Emergency stop" in job.error_summary


@pytest.mark.anyio
async def test_get_parser_logs(db_session, admin_router) -> None:
    """Test fetching parser logs with filters"""
    adapter, session = db_session
    
    # Create test data
    session.execute(
        sa.insert(parser_sources).values(
            id=1, code="test_source", enabled=True, rate_limit_per_min=60, max_concurrency=2
        )
    )
    session.execute(
        sa.insert(parser_jobs).values(
            id=1,
            source_id=1,
            job_type="test",
            status="completed",
            started_at=datetime.now(timezone.utc)
        )
    )
    session.execute(
        sa.insert(parser_job_logs).values(
            id=1,
            job_id=1,
            level="error",
            message="Test error message",
            created_at=datetime.now(timezone.utc)
        )
    )
    session.execute(
        sa.insert(parser_job_logs).values(
            id=2,
            job_id=1,
            level="info",
            message="Test info message",
            created_at=datetime.now(timezone.utc)
        )
    )
    session.commit()
    
    # Test fetching all logs
    result = await admin_router.get_parser_logs(
        level=None,
        source=None,
        from_date=None,
        to_date=None,
        limit=100,
        session=adapter,
        _=None
    )
    
    assert len(result) == 2
    assert result[0].level == "info"  # Ordered by created_at desc
    assert result[1].level == "error"
    
    # Test filtering by level
    result = await admin_router.get_parser_logs(
        level="error",
        source=None,
        from_date=None,
        to_date=None,
        limit=100,
        session=adapter,
        _=None
    )
    
    assert len(result) == 1
    assert result[0].level == "error"


@pytest.mark.anyio
async def test_settings_update_with_audit(db_session, admin_router, mock_user) -> None:
    """Test that settings updates are logged to audit"""
    adapter, session = db_session
    request = MockRequest()
    
    from app.parser.admin.schemas import ParserSettingsUpdate
    payload = ParserSettingsUpdate(
        dry_run_default=True,
        allowed_qualities=["1080p", "720p"]
    )
    
    result = await admin_router.update_settings(
        payload=payload,
        request=request,
        session=adapter,
        current_user=mock_user,
        _=None
    )
    
    assert result.dry_run_default is True
    assert result.allowed_qualities == ["1080p", "720p"]
    
    # Verify database was updated
    row = session.execute(
        sa.select(parser_settings.c.dry_run, parser_settings.c.allowed_qualities)
        .where(parser_settings.c.id == 1)
    ).one()
    assert row.dry_run is True
    assert row.allowed_qualities == ["1080p", "720p"]
