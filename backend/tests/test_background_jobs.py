import asyncio
import importlib
import uuid

import pytest

from app.background.runner import Job, JobRunner, JobStatus
from app.background import default_job_runner
favorites_use_case = importlib.import_module("app.use_cases.favorites.add_favorite")
watch_use_case = importlib.import_module("app.use_cases.watch.update_progress")


@pytest.mark.anyio
async def test_enqueue_executes_job() -> None:
    runner = JobRunner()
    counter = {"count": 0}

    async def handler() -> None:
        counter["count"] += 1

    await runner.enqueue(Job(key="job-1", handler=handler, backoff_seconds=0))
    await asyncio.wait_for(runner.drain(), timeout=1)

    assert counter["count"] == 1
    assert runner.status_for("job-1") == JobStatus.SUCCEEDED
    await runner.stop()


@pytest.mark.anyio
async def test_retry_until_success() -> None:
    runner = JobRunner()
    counter = {"count": 0}

    async def handler() -> None:
        counter["count"] += 1
        if counter["count"] < 3:
            raise RuntimeError("fail")

    await runner.enqueue(
        Job(key="job-retry", handler=handler, max_attempts=3, backoff_seconds=0)
    )
    await asyncio.wait_for(runner.drain(), timeout=1)

    assert counter["count"] == 3
    assert runner.status_for("job-retry") == JobStatus.SUCCEEDED
    await runner.stop()


@pytest.mark.anyio
async def test_duplicate_enqueue_is_idempotent() -> None:
    runner = JobRunner()
    counter = {"count": 0}

    async def handler() -> None:
        counter["count"] += 1

    job = Job(key="job-dup", handler=handler, backoff_seconds=0)
    await runner.enqueue(job)
    await runner.enqueue(job)
    await asyncio.wait_for(runner.drain(), timeout=1)

    assert counter["count"] == 1
    assert runner.status_for("job-dup") == JobStatus.SUCCEEDED
    await runner.stop()


class _DummySession:
    async def commit(self) -> None:  # pragma: no cover - stub
        return None

    async def rollback(self) -> None:  # pragma: no cover - stub
        return None


@pytest.mark.anyio
async def test_add_favorite_job_calls_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}
    runner = JobRunner()

    async def fake_persist(user_id, anime_id, favorite_id, created_at) -> None:  # type: ignore[no-untyped-def]
        called["count"] += 1

    async def fake_get_anime_by_id(_session, _anime_id):  # type: ignore[no-untyped-def]
        return object()

    async def fake_get_favorite(_session, _user_id, _anime_id):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(favorites_use_case, "persist_add_favorite", fake_persist)
    monkeypatch.setattr(favorites_use_case, "get_anime_by_id", fake_get_anime_by_id)
    monkeypatch.setattr(favorites_use_case, "get_favorite", fake_get_favorite)
    monkeypatch.setattr(favorites_use_case, "default_job_runner", runner)
    monkeypatch.setattr("app.background.default_job_runner", runner)

    await favorites_use_case.add_favorite(_DummySession(), uuid.uuid4(), uuid.uuid4())
    await asyncio.wait_for(runner.drain(), timeout=1)
    await runner.stop()

    assert called["count"] == 1


@pytest.mark.anyio
async def test_watch_progress_job_calls_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"count": 0}
    runner = JobRunner()

    async def fake_persist(
        user_id,  # type: ignore[no-untyped-def]
        anime_id,
        episode,
        position_seconds,
        progress_percent,
        *,
        progress_id,
        created_at,
        last_watched_at,
    ) -> None:
        called["count"] += 1

    async def fake_get_anime_by_id(_session, _anime_id):  # type: ignore[no-untyped-def]
        return object()

    async def fake_get_watch_progress(_session, _user_id, _anime_id):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(watch_use_case, "persist_update_progress", fake_persist)
    monkeypatch.setattr(watch_use_case, "get_anime_by_id", fake_get_anime_by_id)
    monkeypatch.setattr(watch_use_case, "get_watch_progress", fake_get_watch_progress)
    monkeypatch.setattr(watch_use_case, "default_job_runner", runner)
    monkeypatch.setattr("app.background.default_job_runner", runner)

    await watch_use_case.update_progress(
        _DummySession(),
        uuid.uuid4(),
        uuid.uuid4(),
        episode=1,
        position_seconds=10,
    )
    await asyncio.wait_for(runner.drain(), timeout=1)
    await runner.stop()

    assert called["count"] == 1
