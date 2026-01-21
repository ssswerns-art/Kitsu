from contextlib import asynccontextmanager
import importlib
import sys
import types

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth import rbac
from app.models.base import Base
from app.parser.admin.schemas import ParserMatchRequest, ParserUnmatchRequest
from app.parser.tables import anime_external, parser_sources


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


@pytest.fixture()
def db_session():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    Base.metadata.create_all(engine, tables=[parser_sources, anime_external])
    session = Session(engine)
    adapter = AsyncSessionAdapter(session, engine)
    yield adapter, session
    session.close()


@pytest.fixture()
def admin_router(monkeypatch: pytest.MonkeyPatch):
    dummy = types.ModuleType("app.dependencies")
    
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

    dummy.get_db = get_db
    dummy.get_current_role = get_current_role
    dummy.get_current_user = get_current_user
    monkeypatch.setitem(sys.modules, "app.dependencies", dummy)
    module = importlib.import_module("app.parser.admin.router")
    return importlib.reload(module)


def test_admin_access_allows_explicit_permissions() -> None:
    """SECURITY-01: Admin should have explicit permissions, not wildcards."""
    admin_perms = rbac.resolve_permissions("admin")
    # No wildcards allowed
    assert "admin:*" not in admin_perms
    # But explicit admin permissions should be present
    assert "admin.parser.settings" in admin_perms
    assert "admin.parser.emergency" in admin_perms
    assert "admin.parser.logs" in admin_perms


def test_admin_access_denies_non_admin() -> None:
    """Non-admin users should not have admin permissions."""
    user_perms = rbac.resolve_permissions("user")
    assert "admin.parser.settings" not in user_perms
    assert "admin.parser.emergency" not in user_perms
    assert "admin.parser.logs" not in user_perms


@pytest.mark.anyio
async def test_match_unmatch_updates_links(db_session, admin_router) -> None:
    adapter, session = db_session
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
        sa.insert(anime_external).values(
            id=10,
            source_id=1,
            external_id="ext-1",
            title_raw="Test",
        )
    )
    session.commit()

    await admin_router.match_anime_external(
        ParserMatchRequest(anime_external_id=10, anime_id="internal-1"),
        session=adapter,
    )
    row = session.execute(
        sa.select(anime_external.c.anime_id, anime_external.c.matched_by).where(
            anime_external.c.id == 10
        )
    ).one()
    assert row.anime_id == "internal-1"
    assert row.matched_by == "manual"
    session.commit()

    await admin_router.unmatch_anime_external(
        ParserUnmatchRequest(anime_external_id=10),
        session=adapter,
    )
    row = session.execute(
        sa.select(anime_external.c.anime_id, anime_external.c.matched_by).where(
            anime_external.c.id == 10
        )
    ).one()
    assert row.anime_id is None
    assert row.matched_by is None
