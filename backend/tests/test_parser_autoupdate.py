from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.base import Base
from app.parser.domain.entities import EpisodeExternal, ScheduleItem
from app.parser.jobs.autoupdate import ParserAutoupdateScheduler
from app.parser.services.autoupdate_service import ParserEpisodeAutoupdateService
from app.parser.tables import (
    anime_episodes_external,
    anime_external,
    anime_external_binding,
    anime_schedule,
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


class StaticScheduleSource:
    def __init__(self, items: list[ScheduleItem]) -> None:
        self._items = items

    def fetch_schedule(self):
        return list(self._items)


class StaticEpisodeSource:
    def __init__(self, items: list[EpisodeExternal]) -> None:
        self._items = items

    def fetch_episodes_for(self, _params=None):
        return list(self._items)


class MockAsyncRedis:
    """Mock async Redis client for testing."""

    def __init__(self):
        self._data: dict[str, str] = {}

    async def ping(self):
        return True

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self._data:
            return False
        self._data[key] = value
        return True

    async def delete(self, key: str) -> int:
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self._data


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
        anime_external_binding,
        anime_schedule,
        anime_episodes_external,
    ]
    Base.metadata.create_all(engine, tables=parser_tables)
    session = Session(engine)
    adapter = AsyncSessionAdapter(session, engine)
    yield adapter, session
    session.close()


def _seed_sources(session: Session) -> None:
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


@pytest.mark.anyio
async def test_autoupdate_detects_new_episode(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter, session = db_session
    def _fail_http(*_args, **_kwargs):
        raise AssertionError("HTTP client should not be used in tests")

    monkeypatch.setattr("httpx.AsyncClient", _fail_http)
    now = datetime.now(timezone.utc)
    _seed_sources(session)
    session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=True,
            update_interval_minutes=30,
            dry_run=False,
            updated_at=now,
        )
    )
    session.execute(
        sa.insert(anime_external).values(
            id=10,
            source_id=1,
            external_id="100",
            title_raw="Test",
            status="ongoing",
        )
    )
    session.execute(
        sa.insert(anime_episodes_external).values(
            anime_id=10,
            source_id=2,
            episode_number=1,
            iframe_url="https://kodik.test/1",
            updated_at=now,
        )
    )
    session.commit()
    schedule_source = StaticScheduleSource(
        [
            ScheduleItem(
                anime_source_id="100",
                episode_number=2,
                airs_at=now,
                source_url="https://shiki.test/animes/100",
            )
        ]
    )
    episode_source = StaticEpisodeSource(
        [
            EpisodeExternal(
                anime_source_id="100",
                number=2,
                stream_url="https://kodik.test/2",
            )
        ]
    )

    service = ParserEpisodeAutoupdateService(
        session=adapter, schedule_source=schedule_source, episode_source=episode_source
    )
    summary = await service.run()

    assert summary["status"] == "success"
    assert summary["episodes"]["inserted"] == 1
    assert (
        session.execute(sa.select(sa.func.count()).select_from(anime_schedule)).scalar_one()
        == 1
    )
    assert (
        session.execute(
            sa.select(sa.func.count()).select_from(anime_episodes_external)
        ).scalar_one()
        == 2
    )


@pytest.mark.anyio
async def test_autoupdate_is_idempotent(db_session) -> None:
    adapter, session = db_session
    now = datetime.now(timezone.utc)
    _seed_sources(session)
    session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=True,
            update_interval_minutes=30,
            dry_run=False,
            updated_at=now,
        )
    )
    session.execute(
        sa.insert(anime_external).values(
            id=10,
            source_id=1,
            external_id="100",
            title_raw="Test",
            status="ongoing",
        )
    )
    session.execute(
        sa.insert(anime_episodes_external).values(
            anime_id=10,
            source_id=2,
            episode_number=1,
            iframe_url="https://kodik.test/1",
            updated_at=now,
        )
    )
    session.commit()
    schedule_source = StaticScheduleSource(
        [ScheduleItem(anime_source_id="100", episode_number=2, airs_at=now)]
    )
    episode_source = StaticEpisodeSource(
        [EpisodeExternal(anime_source_id="100", number=2, stream_url="https://kodik.test/2")]
    )
    service = ParserEpisodeAutoupdateService(
        session=adapter, schedule_source=schedule_source, episode_source=episode_source
    )

    await service.run()
    await service.run()

    assert (
        session.execute(
            sa.select(sa.func.count()).select_from(anime_episodes_external)
        ).scalar_one()
        == 2
    )


@pytest.mark.anyio
async def test_autoupdate_scheduler_disabled(db_session) -> None:
    adapter, session = db_session
    now = datetime.now(timezone.utc)
    _seed_sources(session)
    session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            update_interval_minutes=45,
            dry_run=False,
            updated_at=now,
        )
    )
    session.commit()
    calls: list[object] = []

    def service_factory(**_kwargs):
        calls.append("called")

        class StubService:
            async def run(self, *, force: bool = False) -> dict[str, object]:
                return {"status": "success"}

        return StubService()

    @asynccontextmanager
    async def session_factory():
        yield adapter

    scheduler = ParserAutoupdateScheduler(
        session_factory=session_factory,
        service_factory=service_factory,
        redis_client=MockAsyncRedis(),
    )

    result = await scheduler.run_once()

    assert result["status"] == "disabled"
    assert calls == []


@pytest.mark.anyio
async def test_autoupdate_scheduler_lock_prevents_duplicate_start(db_session) -> None:
    """Test that only one scheduler can start when lock is held."""
    adapter, session = db_session
    now = datetime.now(timezone.utc)
    _seed_sources(session)
    session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=True,
            update_interval_minutes=999999,  # Very long to prevent actual run
            dry_run=False,
            updated_at=now,
        )
    )
    session.commit()

    redis = MockAsyncRedis()

    @asynccontextmanager
    async def session_factory():
        yield adapter

    def service_factory(**_kwargs):
        class StubService:
            async def run(self, *, force: bool = False) -> dict[str, object]:
                return {"status": "success"}

        return StubService()

    # First scheduler acquires lock
    scheduler1 = ParserAutoupdateScheduler(
        session_factory=session_factory,
        service_factory=service_factory,
        redis_client=redis,
    )
    await scheduler1.start()
    assert scheduler1._lock is not None
    assert scheduler1._lock._acquired is True
    assert scheduler1._task is not None

    # Second scheduler cannot acquire lock
    scheduler2 = ParserAutoupdateScheduler(
        session_factory=session_factory,
        service_factory=service_factory,
        redis_client=redis,
    )
    await scheduler2.start()
    assert scheduler2._lock is not None
    assert scheduler2._lock._acquired is False
    assert scheduler2._task is None

    # Cleanup
    await scheduler1.stop()
    await scheduler2.stop()
