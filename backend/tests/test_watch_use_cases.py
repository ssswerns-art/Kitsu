import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import uuid

import pytest

from app.background.runner import JobRunner
from app.errors import NotFoundError
from app.schemas.watch import WatchProgressRead
from app.use_cases.watch.get_continue_watching import get_continue_watching
from app.use_cases.watch.update_progress import update_progress

update_progress_module = importlib.import_module("app.use_cases.watch.update_progress")


@dataclass
class FakeWatchProgress:
    id: uuid.UUID
    user_id: uuid.UUID
    anime_id: uuid.UUID
    episode: int
    position_seconds: int | None
    progress_percent: float | None
    created_at: datetime
    last_watched_at: datetime


class FakeWatchProgressRepository:
    def __init__(self, store: list[FakeWatchProgress], *, anime_exists: bool = True) -> None:
        self._store = store
        self._anime_exists = anime_exists
        self.add_calls = 0
        self.update_calls = 0

    async def anime_exists(self, anime_id: uuid.UUID) -> bool:
        return self._anime_exists

    async def get(
        self, user_id: uuid.UUID, anime_id: uuid.UUID
    ) -> FakeWatchProgress | None:
        return next(
            (
                progress
                for progress in self._store
                if progress.user_id == user_id and progress.anime_id == anime_id
            ),
            None,
        )

    async def list(self, user_id: uuid.UUID, limit: int) -> list[FakeWatchProgress]:
        progress_items = [progress for progress in self._store if progress.user_id == user_id]
        progress_items.sort(key=lambda item: item.last_watched_at, reverse=True)
        return progress_items[:limit]

    async def add(
        self,
        user_id: uuid.UUID,
        anime_id: uuid.UUID,
        episode: int,
        position_seconds: int | None,
        progress_percent: float | None,
        *,
        progress_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
        last_watched_at: datetime | None = None,
    ) -> FakeWatchProgress:
        self.add_calls += 1
        now = datetime.now(timezone.utc)
        progress = FakeWatchProgress(
            id=progress_id or uuid.uuid4(),
            user_id=user_id,
            anime_id=anime_id,
            episode=episode,
            position_seconds=position_seconds,
            progress_percent=progress_percent,
            created_at=created_at or now,
            last_watched_at=last_watched_at or created_at or now,
        )
        self._store.append(progress)
        return progress

    async def update(
        self,
        progress: FakeWatchProgress,
        episode: int,
        position_seconds: int | None,
        progress_percent: float | None,
        *,
        last_watched_at: datetime | None = None,
    ) -> FakeWatchProgress:
        self.update_calls += 1
        progress.episode = episode
        progress.position_seconds = position_seconds
        progress.progress_percent = progress_percent
        if last_watched_at is not None:
            progress.last_watched_at = last_watched_at
        return progress


def build_repo_factory(repo: FakeWatchProgressRepository):
    @asynccontextmanager
    async def factory():
        yield repo

    return factory


@pytest.mark.anyio
async def test_update_progress_enqueues_and_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store: list[FakeWatchProgress] = []
    user_id = uuid.uuid4()
    anime_id = uuid.uuid4()
    repo = FakeWatchProgressRepository(store)
    background_repo = FakeWatchProgressRepository(store)
    runner = JobRunner()

    monkeypatch.setattr(update_progress_module, "default_job_runner", runner)
    monkeypatch.setattr("app.background.default_job_runner", runner)

    result = await update_progress(
        repo,
        user_id=user_id,
        anime_id=anime_id,
        episode=1,
        position_seconds=120,
        progress_percent=25.0,
        watch_repo_factory=build_repo_factory(background_repo),
    )

    await asyncio.wait_for(runner.drain(), timeout=1)
    await runner.stop()

    assert isinstance(result, WatchProgressRead)
    assert background_repo.add_calls == 1
    assert background_repo.update_calls == 0
    assert any(progress.id == result.id for progress in store)


@pytest.mark.anyio
async def test_update_progress_retry_uses_same_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store: list[FakeWatchProgress] = []
    user_id = uuid.uuid4()
    anime_id = uuid.uuid4()
    repo = FakeWatchProgressRepository(store)
    background_repo = FakeWatchProgressRepository(store)
    runner = JobRunner()

    monkeypatch.setattr(update_progress_module, "default_job_runner", runner)
    monkeypatch.setattr("app.background.default_job_runner", runner)

    first = await update_progress(
        repo,
        user_id=user_id,
        anime_id=anime_id,
        episode=1,
        position_seconds=120,
        progress_percent=25.0,
        watch_repo_factory=build_repo_factory(background_repo),
    )
    second = await update_progress(
        repo,
        user_id=user_id,
        anime_id=anime_id,
        episode=1,
        position_seconds=120,
        progress_percent=25.0,
        watch_repo_factory=build_repo_factory(background_repo),
    )

    await asyncio.wait_for(runner.drain(), timeout=1)
    await runner.stop()

    assert first.id == second.id


@pytest.mark.anyio
async def test_update_progress_missing_anime_raises() -> None:
    repo = FakeWatchProgressRepository([], anime_exists=False)

    with pytest.raises(NotFoundError):
        await update_progress(
            repo,
            user_id=uuid.uuid4(),
            anime_id=uuid.uuid4(),
            episode=1,
            position_seconds=0,
        )


@pytest.mark.anyio
async def test_get_continue_watching_returns_sorted() -> None:
    user_id = uuid.uuid4()
    older = FakeWatchProgress(
        id=uuid.uuid4(),
        user_id=user_id,
        anime_id=uuid.uuid4(),
        episode=1,
        position_seconds=10,
        progress_percent=None,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        last_watched_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    newer = FakeWatchProgress(
        id=uuid.uuid4(),
        user_id=user_id,
        anime_id=uuid.uuid4(),
        episode=2,
        position_seconds=20,
        progress_percent=None,
        created_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        last_watched_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
    )
    repo = FakeWatchProgressRepository([older, newer])

    progress = await get_continue_watching(repo, user_id=user_id, limit=10)

    assert progress == [newer, older]
