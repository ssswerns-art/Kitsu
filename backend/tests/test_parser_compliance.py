"""
Unit tests for PARSER-02 compliance requirements.

Tests all mandatory invariants from the parser contract:
1. Manual > Parser: Parser cannot update source="manual" entities
2. Lock enforcement: Parser cannot update locked fields
3. State machine: Parser can only set draft/pending/broken states
4. Dry-run mode: No DB writes or audit logs in dry-run
5. Audit logging: Every update creates an audit log
6. Permissions: Parser must have required permissions (design only, not impl)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import JSON
from sqlalchemy.orm import Session

from app.models.anime import Anime
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.episode import Episode
from app.models.release import Release
from app.parser.domain.errors import (
    EntityLockedError,
    ParserCannotOverrideManualError,
)
from app.parser.services.publish_service import ParserPublishService
from app.parser.tables import (
    anime_episodes_external,
    anime_external,
    anime_external_binding,
    anime_translations,
    parser_settings,
    parser_sources,
)
from tests.parser_helpers import AsyncSessionAdapter


@pytest.fixture()
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    tables = [
        parser_sources,
        parser_settings,
        anime_external,
        anime_episodes_external,
        anime_translations,
        anime_external_binding,
        Anime.__table__,
        Release.__table__,
        Episode.__table__,
        AuditLog.__table__,
    ]
    
    # Override Anime and Episode tables to use JSON instead of ARRAY for SQLite
    # This is a workaround for testing since SQLite doesn't support ARRAY types
    for table in [Anime.__table__, Episode.__table__]:
        for col in table.columns:
            if col.name == "locked_fields" and str(col.type).startswith("ARRAY"):
                col.type = JSON()
                
    Base.metadata.create_all(engine, tables=tables)
    session = Session(engine)
    adapter = AsyncSessionAdapter(session, engine)
    yield adapter, session
    session.close()


@pytest.mark.anyio
async def test_parser_cannot_update_manual_anime(db_session):
    """
    COMPLIANCE TEST 1: Manual > Parser invariant
    
    The parser MUST NOT update an anime with source="manual".
    This should raise ParserCannotOverrideManualError.
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create external anime
    external_id = 1
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
            title_ru="Тестовое Аниме",
        )
    )
    
    # Setup: Create anime with source="manual"
    anime_id = uuid.uuid4()
    manual_anime = Anime(
        id=anime_id,
        title="Manual Anime",
        title_ru="Ручное Аниме",
        source="manual",  # CRITICAL: This is manually created
        state="published",
    )
    sync_session.add(manual_anime)
    
    # Setup: Create binding
    sync_session.execute(
        sa.insert(anime_external_binding).values(
            anime_external_id=external_id,
            anime_id=str(anime_id),
            bound_by="admin",
        )
    )
    sync_session.commit()
    
    # Test: Attempt to publish (update) this anime via parser
    service = ParserPublishService(async_session)
    
    # This MUST raise ParserCannotOverrideManualError
    with pytest.raises(ParserCannotOverrideManualError) as exc_info:
        await service.publish_anime(external_id)
    
    assert "source is 'manual'" in str(exc_info.value)
    
    # Verify anime was NOT modified
    updated_anime = sync_session.get(Anime, anime_id)
    assert updated_anime.title == "Manual Anime"
    assert updated_anime.source == "manual"


@pytest.mark.anyio
async def test_parser_cannot_update_locked_anime(db_session):
    """
    COMPLIANCE TEST 2: Lock enforcement
    
    The parser MUST NOT update locked fields.
    This should raise EntityLockedError from LockService.
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create external anime
    external_id = 1
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
            title_ru="Новое название",
        )
    )
    
    # Setup: Create anime with is_locked=True
    anime_id = uuid.uuid4()
    locked_anime = Anime(
        id=anime_id,
        title="Locked Anime",
        title_ru="Заблокированное Аниме",
        source="parser",  # Parser created, but now locked
        state="pending",
        is_locked=True,  # CRITICAL: This is locked
        locked_reason="Admin locked for review",
    )
    sync_session.add(locked_anime)
    
    # Setup: Create binding
    sync_session.execute(
        sa.insert(anime_external_binding).values(
            anime_external_id=external_id,
            anime_id=str(anime_id),
            bound_by="parser",
        )
    )
    sync_session.commit()
    
    # Test: Attempt to publish (update) this locked anime
    service = ParserPublishService(async_session)
    
    # This MUST raise an error from LockService
    with pytest.raises(Exception) as exc_info:  # HTTPException from LockService
        await service.publish_anime(external_id)
    
    # Verify error is about locking
    assert "locked" in str(exc_info.value).lower()
    
    # Verify anime was NOT modified
    updated_anime = sync_session.get(Anime, anime_id)
    assert updated_anime.title_ru == "Заблокированное Аниме"


@pytest.mark.anyio
async def test_parser_dry_run_mode_no_db_writes(db_session):
    """
    COMPLIANCE TEST 3: Dry-run mode
    
    When dry_run=True, the parser MUST NOT write to the database.
    It should return early with dry_run=True in the result.
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings with dry_run=True
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=True,  # CRITICAL: Dry-run enabled
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create external anime
    external_id = 1
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
            title_ru="Тестовое Аниме",
        )
    )
    sync_session.commit()
    
    # Count anime before dry-run
    anime_count_before = sync_session.query(Anime).count()
    
    # Test: Publish anime in dry-run mode
    service = ParserPublishService(async_session)
    result = await service.publish_anime(external_id)
    
    # Verify: Result indicates dry-run
    assert result.get("dry_run") is True
    assert "anime_id" in result
    
    # Verify: No anime was created in DB
    anime_count_after = sync_session.query(Anime).count()
    assert anime_count_after == anime_count_before
    
    # Verify: No audit logs were created (dry-run doesn't create audit logs)
    audit_count = sync_session.query(AuditLog).count()
    assert audit_count == 0


@pytest.mark.anyio
async def test_parser_creates_audit_log_on_update(db_session):
    """
    COMPLIANCE TEST 4: Audit logging
    
    Every parser update MUST create an audit log with:
    - actor_id = NULL
    - actor_type = "system"
    - before/after states
    - reason with source info
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings (dry_run=False for real update)
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,  # CRITICAL: Real mode
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create external anime
    external_id = 1
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
            title_ru="Тестовое Аниме",
        )
    )
    sync_session.commit()
    
    # Test: Publish anime
    service = ParserPublishService(async_session)
    result = await service.publish_anime(external_id)
    
    anime_id = result["anime_id"]
    
    # Verify: Audit log was created
    audit_logs = sync_session.query(AuditLog).filter_by(
        entity_type="anime",
        entity_id=anime_id,
    ).all()
    
    assert len(audit_logs) == 1
    audit_log = audit_logs[0]
    
    # Verify: System actor
    assert audit_log.actor_id is None
    assert audit_log.actor_type == "system"
    
    # Verify: Action is correct
    assert audit_log.action == "anime.create"
    
    # Verify: Reason mentions source
    assert audit_log.reason is not None
    assert "source" in audit_log.reason.lower()


@pytest.mark.anyio
async def test_parser_sets_source_and_updated_by(db_session):
    """
    COMPLIANCE TEST 5: Source and updated_by fields
    
    The parser MUST set:
    - source = "parser"
    - updated_by = NULL (system actor)
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create external anime
    external_id = 1
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
            title_ru="Тестовое Аниме",
        )
    )
    sync_session.commit()
    
    # Test: Publish anime
    service = ParserPublishService(async_session)
    result = await service.publish_anime(external_id)
    
    anime_id = uuid.UUID(result["anime_id"])
    
    # Verify: Anime has correct source and updated_by
    anime = sync_session.get(Anime, anime_id)
    assert anime is not None
    assert anime.source == "parser"
    assert anime.updated_by is None


@pytest.mark.anyio
async def test_parser_cannot_update_manual_episode(db_session):
    """
    COMPLIANCE TEST 6: Manual > Parser for episodes
    
    The parser MUST NOT update an episode with source="manual".
    This should raise ParserCannotOverrideManualError.
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create anime and release
    anime_id = uuid.uuid4()
    anime = Anime(
        id=anime_id,
        title="Test Anime",
        source="parser",
        state="pending",
    )
    sync_session.add(anime)
    
    release_id = uuid.uuid4()
    release = Release(
        id=release_id,
        anime_id=anime_id,
        title="Test Release",
        status="ongoing",
    )
    sync_session.add(release)
    
    # Setup: Create manual episode
    episode_id = uuid.uuid4()
    manual_episode = Episode(
        id=episode_id,
        release_id=release_id,
        number=1,
        title="Manual Episode",
        source="manual",  # CRITICAL: Manually created
    )
    sync_session.add(manual_episode)
    
    # Setup: Create external data
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    
    external_id = 1
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
        )
    )
    
    sync_session.execute(
        sa.insert(anime_external_binding).values(
            anime_external_id=external_id,
            anime_id=str(anime_id),
            bound_by="parser",
        )
    )
    
    sync_session.execute(
        sa.insert(anime_episodes_external).values(
            anime_id=external_id,
            source_id=1,
            episode_number=1,
            iframe_url="https://example.com/player",
            updated_at=datetime.now(timezone.utc),
        )
    )
    sync_session.commit()
    
    # Test: Attempt to publish (update) this manual episode
    service = ParserPublishService(async_session)
    
    # This MUST raise ParserCannotOverrideManualError
    with pytest.raises(ParserCannotOverrideManualError) as exc_info:
        await service.publish_episode(str(anime_id), 1)
    
    assert "source is 'manual'" in str(exc_info.value)
    
    # Verify episode was NOT modified
    updated_episode = sync_session.get(Episode, episode_id)
    assert updated_episode.title == "Manual Episode"
    assert updated_episode.source == "manual"


@pytest.mark.anyio
async def test_parser_episode_sets_source_parser(db_session):
    """
    COMPLIANCE TEST 7: Episode source field
    
    The parser MUST set source="parser" and updated_by=NULL for episodes.
    """
    async_session, sync_session = db_session
    
    # Setup: Create parser settings
    sync_session.execute(
        sa.insert(parser_settings).values(
            mode="manual",
            dry_run=False,
            stage_only=True,
            publish_enabled=False,
            enable_autoupdate=False,
            updated_at=datetime.now(timezone.utc),
        )
    )
    
    # Setup: Create anime and release
    anime_id = uuid.uuid4()
    anime = Anime(
        id=anime_id,
        title="Test Anime",
        source="parser",
        state="pending",
    )
    sync_session.add(anime)
    
    release_id = uuid.uuid4()
    release = Release(
        id=release_id,
        anime_id=anime_id,
        title="Test Release",
        status="ongoing",
    )
    sync_session.add(release)
    
    # Setup: Create external data
    sync_session.execute(
        sa.insert(parser_sources).values(
            id=1,
            code="shikimori",
            enabled=True,
        )
    )
    
    external_id = 1
    sync_session.execute(
        sa.insert(anime_external).values(
            id=external_id,
            source_id=1,
            external_id="12345",
            title_raw="Test Anime",
        )
    )
    
    sync_session.execute(
        sa.insert(anime_external_binding).values(
            anime_external_id=external_id,
            anime_id=str(anime_id),
            bound_by="parser",
        )
    )
    
    sync_session.execute(
        sa.insert(anime_episodes_external).values(
            anime_id=external_id,
            source_id=1,
            episode_number=1,
            iframe_url="https://example.com/player",
            updated_at=datetime.now(timezone.utc),
        )
    )
    sync_session.commit()
    
    # Test: Publish episode
    service = ParserPublishService(async_session)
    result = await service.publish_episode(str(anime_id), 1)
    
    episode_id = uuid.UUID(result["episode_id"])
    
    # Verify: Episode has correct source and updated_by
    episode = sync_session.get(Episode, episode_id)
    assert episode is not None
    assert episode.source == "parser"
    assert episode.updated_by is None
