import asyncio
import os
import uuid
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient

# Ensure required environment variables are present for module imports.
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
)

from app.auth.enforcement_matrix import ENFORCEMENT_MATRIX
from app.auth.helpers import require_any_permission, require_permission
from app.dependencies import get_current_role, get_current_user, get_db
from app.errors import PermissionError
from app.routers import favorites, watch
from app.main import handle_http_exception


def make_request(path: str = "/favorites") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
        }
    )


def test_require_permission_allows_user_write() -> None:
    checker = require_permission("write:content")
    asyncio.run(checker(role="user", request=make_request("/favorites")))


def test_require_permission_denies_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    checker = require_permission("write:profile")
    with caplog.at_level("WARNING"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(checker(role="guest", request=make_request("/favorites")))
    assert exc.value.status_code == 403
    assert PermissionError.message in exc.value.detail
    assert any("write:profile" in record.getMessage() for record in caplog.records)
    assert any("/favorites" in record.getMessage() for record in caplog.records)
    assert any("GET" in record.getMessage() for record in caplog.records)


def test_require_any_permission_allows_when_one_matches() -> None:
    checker = require_any_permission(["write:profile", "read:content"])
    asyncio.run(checker(role="user", request=make_request("/favorites")))


class DummySession:
    async def commit(self) -> None:  # pragma: no cover - stub
        return None

    async def rollback(self) -> None:  # pragma: no cover - stub
        return None

    async def refresh(self, _obj: object) -> None:  # pragma: no cover - stub
        return None


class DummyUser:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.email = "user@example.com"
        self.avatar = None
        self.is_active = True
        self.created_at = datetime.now()


class DummyFavorite:
    def __init__(self, anime_id: uuid.UUID) -> None:
        self.id = uuid.uuid4()
        self.anime_id = anime_id
        self.created_at = datetime.now()


class DummyProgress:
    def __init__(
        self,
        anime_id: uuid.UUID,
        episode: int,
        position_seconds: int | None,
        progress_percent: float | None,
    ) -> None:
        now = datetime.now()
        self.id = uuid.uuid4()
        self.anime_id = anime_id
        self.episode = episode
        self.position_seconds = position_seconds
        self.progress_percent = progress_percent
        self.created_at = now
        self.last_watched_at = now


def make_client(role: str, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def fake_add_favorite_use_case(
        _db: DummySession, user_id: uuid.UUID, anime_id: uuid.UUID
    ) -> DummyFavorite:
        return DummyFavorite(anime_id)

    async def fake_remove_favorite_use_case(
        _db: DummySession, user_id: uuid.UUID, anime_id: uuid.UUID
    ) -> None:
        pass

    async def fake_update_progress(
        _db: DummySession,
        user_id: uuid.UUID,
        anime_id: uuid.UUID,
        episode: int,
        position_seconds: int | None = None,
        progress_percent: float | None = None,
    ) -> DummyProgress:
        return DummyProgress(anime_id, episode, position_seconds, progress_percent)

    monkeypatch.setattr(favorites, "add_favorite_use_case", fake_add_favorite_use_case)
    monkeypatch.setattr(favorites, "remove_favorite_use_case", fake_remove_favorite_use_case)
    monkeypatch.setattr(watch, "update_progress", fake_update_progress)

    app = FastAPI()
    app.include_router(favorites.router)
    app.include_router(watch.router)
    app.add_exception_handler(HTTPException, handle_http_exception)
    @app.post("/unlisted")
    async def create_unlisted() -> dict:
        return {"message": "ok"}

    dummy_user = DummyUser()

    async def override_role() -> str:
        return role

    async def override_user() -> DummyUser:
        return dummy_user

    async def override_db():
        yield DummySession()

    app.dependency_overrides[get_current_role] = override_role
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db

    return TestClient(app)


def test_delete_favorite_enforced_allows_user(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("user", monkeypatch)
    response = client.delete(f"/favorites/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_delete_favorite_enforced_denies_guest(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("guest", monkeypatch)
    response = client.delete(f"/favorites/{uuid.uuid4()}")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["message"] == PermissionError.message


def test_create_favorite_enforced_allows_user(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("user", monkeypatch)
    payload = {"anime_id": str(uuid.uuid4())}
    response = client.post("/favorites/", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["anime_id"] == payload["anime_id"]


def test_create_favorite_enforced_denies_guest(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("guest", monkeypatch)
    payload = {"anime_id": str(uuid.uuid4())}
    response = client.post("/favorites/", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["message"] == PermissionError.message


def test_watch_progress_enforced_allows_user(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("user", monkeypatch)
    payload = {
        "anime_id": str(uuid.uuid4()),
        "episode": 1,
        "position_seconds": 30,
    }
    response = client.post("/watch/progress", json=payload)
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["anime_id"] == payload["anime_id"]
    assert body["episode"] == payload["episode"]


def test_watch_progress_enforced_denies_guest(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("guest", monkeypatch)
    payload = {
        "anime_id": str(uuid.uuid4()),
        "episode": 1,
        "position_seconds": 30,
    }
    response = client.post("/watch/progress", json=payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error"]["message"] == PermissionError.message
def test_enforcement_matrix_scope_locked() -> None:
    expected_paths = {
        ("POST", "/favorites"),
        ("DELETE", "/favorites/{anime_id}"),
        ("POST", "/watch/progress"),
    }
    assert set(ENFORCEMENT_MATRIX.keys()) == expected_paths


def test_unlisted_endpoint_not_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client("guest", monkeypatch)
    response = client.post("/unlisted")
    assert response.status_code == status.HTTP_200_OK
