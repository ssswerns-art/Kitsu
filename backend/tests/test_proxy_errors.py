import os

import httpx
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
import pytest
from starlette.exceptions import HTTPException as StarletteHTTPException

# Ensure required environment variables are present for module imports.
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
)

from app.api.router import router  # noqa: E402
from app.main import handle_http_exception  # noqa: E402


class DummyClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def __aenter__(self) -> "DummyClient":  # pragma: no cover - context stub
        return self

    async def __aexit__(self, *_args) -> None:  # pragma: no cover - context stub
        return None

    async def get(self, *_args, **_kwargs):
        raise self.exc


def make_status_error(code: int) -> httpx.HTTPStatusError:
    response = httpx.Response(code, request=httpx.Request("GET", "http://upstream"))
    return httpx.HTTPStatusError(
        "upstream error", request=response.request, response=response
    )


def make_app() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    return TestClient(app)


def test_search_suggestion_upstream_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_client():
        return DummyClient(make_status_error(status.HTTP_404_NOT_FOUND))

    monkeypatch.setattr("app.api.proxy.search.get_client", fake_get_client)
    client = make_app()

    response = client.get("/api/search/suggestion", params={"q": "naruto"})

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["error"]["message"] == "Upstream request was rejected"


def test_anime_info_upstream_500(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_client():
        return DummyClient(make_status_error(status.HTTP_500_INTERNAL_SERVER_ERROR))

    monkeypatch.setattr("app.api.proxy.anime.get_client", fake_get_client)
    client = make_app()

    response = client.get("/api/anime/any-slug")

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json()["error"]["message"] == "Upstream service unavailable"


def test_anime_episodes_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "http://upstream")
    async def fake_get_client():
        return DummyClient(httpx.ReadTimeout("timeout", request=request))

    monkeypatch.setattr("app.api.proxy.anime.get_client", fake_get_client)
    client = make_app()

    response = client.get("/api/anime/any-slug/episodes")

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert response.json()["error"]["message"] == "Upstream service unavailable"
