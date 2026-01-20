import uuid
from datetime import datetime, timezone

import pytest

from app.crud import refresh_token as refresh_token_crud
from app.crud import user as user_crud
from app.crud.refresh_token import RefreshTokenRepository
from app.crud.user import UserRepository


class DummySession:
    def __init__(self) -> None:
        self.added = None
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, instance) -> None:  # type: ignore[no-untyped-def]
        self.added = instance

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.mark.anyio
async def test_user_repository_get_by_email_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummySession()
    sentinel = object()

    async def fake_get_user_by_email(session_arg, email):  # type: ignore[no-untyped-def]
        assert session_arg is session
        assert email == "user@example.com"
        return sentinel

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)

    repo = UserRepository(session)

    result = await repo.get_by_email("user@example.com")

    assert result is sentinel


@pytest.mark.anyio
async def test_user_repository_create_adds_and_flushes() -> None:
    session = DummySession()
    repo = UserRepository(session)

    user = await repo.create("user@example.com", "hash")

    assert session.added is user
    assert session.flushed is True
    assert user.email == "user@example.com"
    assert user.password_hash == "hash"


@pytest.mark.anyio
async def test_refresh_token_repository_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummySession()
    create_sentinel = object()
    get_sentinel = object()
    revoke_sentinel = object()

    async def fake_create(  # type: ignore[no-untyped-def]
        session_arg, user_id, token_hash, expires_at
    ):
        assert session_arg is session
        assert user_id == uuid.UUID(int=1)
        assert token_hash == "token-hash"
        assert expires_at == datetime(2030, 1, 1, tzinfo=timezone.utc)
        return create_sentinel

    async def fake_get(  # type: ignore[no-untyped-def]
        session_arg, token_hash, *, for_update=False
    ):
        assert session_arg is session
        assert token_hash == "token-hash"
        assert for_update is True
        return get_sentinel

    async def fake_get_by_user_id(  # type: ignore[no-untyped-def]
        session_arg, user_id, *, for_update=False
    ):
        assert session_arg is session
        assert user_id == uuid.UUID(int=3)
        assert for_update is False
        return get_sentinel

    async def fake_revoke(session_arg, user_id):  # type: ignore[no-untyped-def]
        assert session_arg is session
        assert user_id == uuid.UUID(int=2)
        return revoke_sentinel

    monkeypatch.setattr(
        refresh_token_crud, "create_or_rotate_refresh_token", fake_create
    )
    monkeypatch.setattr(refresh_token_crud, "get_refresh_token_by_hash", fake_get)
    monkeypatch.setattr(
        refresh_token_crud, "get_refresh_token_by_user_id", fake_get_by_user_id
    )
    monkeypatch.setattr(refresh_token_crud, "revoke_refresh_token", fake_revoke)

    repo = RefreshTokenRepository(session)

    assert (
        await repo.create_or_rotate(
            uuid.UUID(int=1),
            "token-hash",
            datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        is create_sentinel
    )
    assert await repo.get_by_hash("token-hash", for_update=True) is get_sentinel
    assert await repo.get_by_user_id(uuid.UUID(int=3)) is get_sentinel
    assert await repo.revoke(uuid.UUID(int=2)) is revoke_sentinel

    await repo.commit()
    await repo.rollback()

    assert session.committed is True
    assert session.rolled_back is True
