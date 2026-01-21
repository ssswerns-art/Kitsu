from __future__ import annotations

from contextlib import asynccontextmanager
import importlib
import sys
import types
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.base import Base
from app.parser.admin.schemas import ParserSettingsUpdate
from app.parser.config import ParserSettings
from app.parser.domain.entities import AnimeExternal, EpisodeExternal, ScheduleItem, TranslationExternal
from app.parser.services.sync_service import ParserSyncService
from app.parser.tables import (
    anime_episodes_external,
    anime_external,
    anime_schedule,
    anime_translations,
    parser_job_logs,
    parser_jobs,
    parser_settings,
    parser_sources,
)


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


class StaticCatalogSource:
    def __init__(self, items: list[AnimeExternal]) -> None:
        self._items = items

    def fetch_catalog(self):
        return list(self._items)


class StaticScheduleSource:
    def __init__(self, items: list[ScheduleItem]) -> None:
        self._items = items

    def fetch_schedule(self):
        return list(self._items)


class StaticEpisodeSource:
    def __init__(self, items: list[EpisodeExternal]) -> None:
        self._items = items

    def fetch_episodes(self):
        return list(self._items)


@pytest.fixture()
def db_session():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    parser_tables = [
        parser_sources,
        parser_settings,
        parser_jobs,
        parser_job_logs,
        anime_external,
        anime_schedule,
        anime_episodes_external,
        anime_translations,
    ]
    Base.metadata.create_all(engine, tables=parser_tables)
    session = Session(engine)
    adapter = AsyncSessionAdapter(session, engine)
    yield adapter, session
    session.close()


@pytest.fixture()
def admin_router(monkeypatch: pytest.MonkeyPatch):
    dummy = types.ModuleType("app.dependencies")
    audit_module = types.ModuleType("app.services.audit.audit_service")
    
    # Create a mock user
    mock_user = types.SimpleNamespace()
    mock_user.id = "test-user-id"
    mock_user.role = "admin"
    mock_user.is_admin = True

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


@pytest.mark.anyio
async def test_settings_save_and_reload(db_session, admin_router) -> None:
    adapter, session = db_session
    
    # Create a mock request object
    mock_request = types.SimpleNamespace()
    mock_request.client = types.SimpleNamespace()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {"user-agent": "test-agent"}
    
    # Create a mock user
    mock_user = types.SimpleNamespace()
    mock_user.id = "test-user-id"
    
    payload = ParserSettingsUpdate(
        allowed_translations=["AniLibria"],
        allowed_translation_types=["voice"],
        allowed_qualities=["1080p"],
        preferred_translation_priority=["AniLibria"],
        preferred_quality_priority=["1080p"],
        blacklist_titles=["Forbidden"],
        blacklist_external_ids=["999"],
        autopublish_enabled=True,
        stage_only=False,
        dry_run_default=False,
    )

    settings = await admin_router.update_settings(
        payload, 
        request=mock_request,
        session=adapter,
        current_user=mock_user,
        _=None
    )

    assert settings.autopublish_enabled is False
    assert settings.stage_only is True
    assert settings.dry_run_default is False
    assert settings.allowed_translations == ["AniLibria"]
    row = session.execute(sa.select(parser_settings)).mappings().one()
    assert row["publish_enabled"] is False
    assert row["stage_only"] is True
    assert row["dry_run"] is False
    assert row["allowed_translations"] == ["AniLibria"]
    assert row["blacklist_external_ids"] == ["999"]


@pytest.mark.anyio
async def test_filtering_and_blacklist_applies_before_persist(db_session) -> None:
    adapter, session = db_session
    settings = ParserSettings(
        allowed_translations=["AniLibria"],
        allowed_translation_types=["voice"],
        allowed_qualities=["1080p"],
        preferred_translation_priority=["AniLibria"],
        preferred_quality_priority=["1080p"],
        blacklist_titles=["Blacklisted"],
        blacklist_external_ids=["2"],
    )
    session.execute(
        sa.insert(parser_settings).values(
            mode=settings.mode,
            stage_only=True,
            publish_enabled=False,
            dry_run=settings.dry_run_default,
            allowed_translation_types=list(settings.allowed_translation_types),
            allowed_translations=list(settings.allowed_translations),
            allowed_qualities=list(settings.allowed_qualities),
            preferred_translation_priority=list(settings.preferred_translation_priority),
            preferred_quality_priority=list(settings.preferred_quality_priority),
            blacklist_titles=list(settings.blacklist_titles),
            blacklist_external_ids=list(settings.blacklist_external_ids),
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()

    catalog = [
        AnimeExternal(source_id="1", title="Allowed", year=2024, status="ongoing"),
        AnimeExternal(source_id="2", title="Blacklisted", year=2023, status="ended"),
    ]
    schedule = [
        ScheduleItem(anime_source_id="1", episode_number=1),
        ScheduleItem(anime_source_id="2", episode_number=1),
    ]
    episodes = [
        EpisodeExternal(
            anime_source_id="1",
            number=1,
            stream_url="https://kodik.test/embed/1",
            translations=[
                TranslationExternal(code="tr1", name="AniLibria", type="voice"),
                TranslationExternal(code="tr2", name="Subs", type="sub"),
            ],
            qualities=["720p", "1080p"],
        ),
        EpisodeExternal(
            anime_source_id="2",
            number=1,
            stream_url="https://kodik.test/embed/2",
            translations=[TranslationExternal(code="tr3", name="AniDub", type="voice")],
            qualities=["720p"],
        ),
    ]

    service = ParserSyncService(
        StaticCatalogSource(catalog),
        StaticEpisodeSource(episodes),
        StaticScheduleSource(schedule),
        session=adapter,
    )

    service.sync_all()

    assert session.execute(
        sa.select(sa.func.count()).select_from(anime_external)
    ).scalar_one() == 1
    assert session.execute(
        sa.select(sa.func.count()).select_from(anime_schedule)
    ).scalar_one() == 1
    assert session.execute(
        sa.select(sa.func.count()).select_from(anime_episodes_external)
    ).scalar_one() == 1
    assert session.execute(
        sa.select(sa.func.count()).select_from(anime_translations)
    ).scalar_one() == 1
    row = session.execute(
        sa.select(
            anime_episodes_external.c.available_qualities,
            anime_episodes_external.c.available_translations,
        )
    ).one()
    assert row.available_qualities == ["1080p"]
    assert row.available_translations == ["AniLibria"]
