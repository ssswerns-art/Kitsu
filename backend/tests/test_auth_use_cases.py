import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/db"
)

from app.application.auth_rate_limit import auth_rate_limiter  # noqa: E402
from app.errors import PermissionError, ValidationError  # noqa: E402
from app.use_cases.auth.login_user import login_user  # noqa: E402
from app.use_cases.auth.logout_user import logout_user  # noqa: E402
from app.use_cases.auth.refresh_session import refresh_session  # noqa: E402
from app.use_cases.auth.register_user import register_user  # noqa: E402
from app.utils.security import (  # noqa: E402
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass
class FakeUser:
    id: uuid.UUID
    email: str
    password_hash: str


@dataclass
class FakeRefreshToken:
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    revoked: bool = False


class FakeUserPort:
    def __init__(self, existing_user: FakeUser | None = None) -> None:
        self.existing_user = existing_user
        self.created_user: FakeUser | None = None
        self.last_email: str | None = None

    async def get_by_email(self, email: str) -> FakeUser | None:
        self.last_email = email
        return self.existing_user

    async def create(self, email: str, password_hash: str) -> FakeUser:
        user = FakeUser(id=uuid.uuid4(), email=email, password_hash=password_hash)
        self.created_user = user
        return user


class FakeTokenPort:
    def __init__(self, stored_token: FakeRefreshToken | None = None) -> None:
        self.stored_token = stored_token
        self.created_token: FakeRefreshToken | None = None
        self.revoked_user_id: uuid.UUID | None = None
        self.committed = False
        self.rolled_back = False
        self.last_hash: str | None = None

    async def create_or_rotate(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> FakeRefreshToken:
        token = FakeRefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
        self.created_token = token
        self.stored_token = token
        return token

    async def get_by_hash(
        self, token_hash: str, *, for_update: bool = False
    ) -> FakeRefreshToken | None:
        self.last_hash = token_hash
        return self.stored_token

    async def get_by_user_id(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> FakeRefreshToken | None:
        if self.stored_token and self.stored_token.user_id == user_id:
            return self.stored_token
        return None

    async def revoke(self, user_id: uuid.UUID) -> FakeRefreshToken | None:
        self.revoked_user_id = user_id
        if self.stored_token:
            self.stored_token.revoked = True
        return self.stored_token

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> None:
    auth_rate_limiter.clear()


@pytest.mark.anyio
async def test_register_user_creates_user_and_tokens() -> None:
    user_port = FakeUserPort()
    token_port = FakeTokenPort()

    tokens = await register_user(user_port, token_port, "user@example.com", "secret")

    assert user_port.created_user is not None
    assert verify_password("secret", user_port.created_user.password_hash)
    assert token_port.created_token is not None
    assert token_port.created_token.user_id == user_port.created_user.id
    assert token_port.created_token.token_hash == hash_refresh_token(tokens.refresh_token)
    assert token_port.committed is True


@pytest.mark.anyio
async def test_register_user_duplicate_rolls_back() -> None:
    user_port = FakeUserPort(
        existing_user=FakeUser(
            id=uuid.uuid4(), email="user@example.com", password_hash="hash"
        )
    )
    token_port = FakeTokenPort()

    with pytest.raises(ValidationError):
        await register_user(user_port, token_port, "user@example.com", "secret")

    assert user_port.created_user is None
    assert token_port.rolled_back is True


@pytest.mark.anyio
async def test_login_user_commits_tokens() -> None:
    user = FakeUser(
        id=uuid.uuid4(), email="user@example.com", password_hash=hash_password("secret")
    )
    user_port = FakeUserPort(existing_user=user)
    token_port = FakeTokenPort()

    tokens = await login_user(user_port, token_port, "user@example.com", "secret")

    assert tokens.access_token
    assert token_port.created_token is not None
    assert token_port.created_token.user_id == user.id
    assert token_port.committed is True


@pytest.mark.anyio
async def test_refresh_session_revoked_token_rolls_back() -> None:
    refresh_token = create_refresh_token()
    token_hash = hash_refresh_token(refresh_token)
    stored_token = FakeRefreshToken(
        user_id=uuid.uuid4(),
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        revoked=True,
    )
    token_port = FakeTokenPort(stored_token=stored_token)

    with pytest.raises(PermissionError):
        await refresh_session(token_port, refresh_token, client_ip="127.0.0.1")

    assert token_port.rolled_back is True


@pytest.mark.anyio
async def test_logout_user_revokes_token() -> None:
    stored_token = FakeRefreshToken(
        user_id=uuid.uuid4(),
        token_hash="hash",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    token_port = FakeTokenPort(stored_token=stored_token)

    await logout_user(token_port, "refresh-token")

    assert token_port.revoked_user_id == stored_token.user_id
    assert token_port.committed is True


@pytest.mark.anyio
async def test_logout_user_uses_user_id_when_token_missing() -> None:
    user_id = uuid.uuid4()
    token_port = FakeTokenPort()

    await logout_user(token_port, "missing-token", user_id=user_id)

    assert token_port.revoked_user_id == user_id
    assert token_port.committed is True
