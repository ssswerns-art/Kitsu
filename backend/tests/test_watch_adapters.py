import uuid
from datetime import datetime, timezone
from typing import Any, TypeVar, cast

import pytest

from app.crud import watch_progress as watch_progress_crud
from app.crud.watch_progress import WatchProgressRepository
from app.models.anime import Anime

T = TypeVar("T")


class DummySession:
    def __init__(self, get_result: T | None = None) -> None:
        self.get_result = get_result
        self.get_args = None
        self.commit_calls = 0
        self.rollback_calls = 0

    async def get(self, model: type[T], key: Any) -> T | None:
        self.get_args = (model, key)
        return cast(T | None, self.get_result)

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.mark.anyio
async def test_watch_progress_repository_anime_exists() -> None:
    session = DummySession(get_result=object())
    repo = WatchProgressRepository(session)
    anime_id = uuid.uuid4()

    assert await repo.anime_exists(anime_id) is True
    assert session.get_args == (Anime, anime_id)


@pytest.mark.anyio
async def test_watch_progress_repository_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummySession()
    get_sentinel = object()
    list_sentinel = [object()]
    add_sentinel = object()
    update_sentinel = object()

    async def fake_get(
        session_arg: DummySession, user_id: uuid.UUID, anime_id: uuid.UUID
    ) -> object:
        assert session_arg is session
        assert user_id == uuid.UUID(int=1)
        assert anime_id == uuid.UUID(int=2)
        return get_sentinel

    async def fake_list(
        session_arg: DummySession, user_id: uuid.UUID, limit: int
    ) -> list[object]:
        assert session_arg is session
        assert user_id == uuid.UUID(int=3)
        assert limit == 5
        return list_sentinel

    async def fake_add(
        session_arg: DummySession,
        user_id: uuid.UUID,
        anime_id: uuid.UUID,
        episode: int,
        position_seconds: int | None,
        progress_percent: float | None,
        progress_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        last_watched_at: datetime | None = None,
    ) -> object:
        assert session_arg is session
        assert user_id == uuid.UUID(int=4)
        assert anime_id == uuid.UUID(int=5)
        assert episode == 7
        assert position_seconds == 11
        assert progress_percent == 12.5
        assert progress_id == uuid.UUID(int=6)
        assert created_at == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert last_watched_at == datetime(2024, 2, 1, tzinfo=timezone.utc)
        return add_sentinel

    async def fake_update(
        session_arg: DummySession,
        progress: object,
        episode: int,
        position_seconds: int | None,
        progress_percent: float | None,
        last_watched_at: datetime | None = None,
    ) -> object:
        assert session_arg is session
        assert progress is get_sentinel
        assert episode == 8
        assert position_seconds == 15
        assert progress_percent == 50.0
        assert last_watched_at == datetime(2024, 3, 1, tzinfo=timezone.utc)
        return update_sentinel

    monkeypatch.setattr(watch_progress_crud, "get_watch_progress", fake_get)
    monkeypatch.setattr(watch_progress_crud, "list_watch_progress", fake_list)
    monkeypatch.setattr(watch_progress_crud, "create_watch_progress", fake_add)
    monkeypatch.setattr(watch_progress_crud, "update_watch_progress", fake_update)

    repo = WatchProgressRepository(session)

    assert await repo.get(uuid.UUID(int=1), uuid.UUID(int=2)) is get_sentinel
    assert await repo.list(uuid.UUID(int=3), limit=5) is list_sentinel
    assert (
        await repo.add(
            uuid.UUID(int=4),
            uuid.UUID(int=5),
            7,
            11,
            12.5,
            progress_id=uuid.UUID(int=6),
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            last_watched_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        is add_sentinel
    )
    assert (
        await repo.update(
            get_sentinel,
            8,
            15,
            50.0,
            last_watched_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        is update_sentinel
    )
    assert session.commit_calls == 2
    assert session.rollback_calls == 0


@pytest.mark.anyio
async def test_watch_progress_repository_rolls_back_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = DummySession()

    async def fake_add(*_args, **_kwargs) -> object:  # type: ignore[no-untyped-def]
        raise RuntimeError("fail")

    monkeypatch.setattr(watch_progress_crud, "create_watch_progress", fake_add)

    repo = WatchProgressRepository(session)

    with pytest.raises(RuntimeError, match="fail"):
        await repo.add(uuid.uuid4(), uuid.uuid4(), 1, 10, 20.0)

    assert session.commit_calls == 0
    assert session.rollback_calls == 1

