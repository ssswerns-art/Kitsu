from datetime import datetime, timezone
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .crud.favorite import FavoriteRepository
from .crud.watch_progress import WatchProgressRepository
from .crud.refresh_token import RefreshTokenRepository
from .crud.user import UserRepository
from .database import AsyncSessionLocal, get_session
from .domain.ports.favorite import (
    FavoriteRepository as FavoriteRepositoryPort,
    FavoriteRepositoryFactory,
)
from .domain.ports.watch_progress import (
    WatchProgressRepository as WatchProgressRepositoryPort,
    WatchProgressRepositoryFactory,
)
from .domain.ports.token import RefreshTokenPort
from .domain.ports.user import UserPort
from .auth import rbac
from .models.user import User
from .security.token_inspection import ExpiredTokenError, InvalidTokenError, validate_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_user_port(db: AsyncSession = Depends(get_db)) -> UserPort:
    return UserRepository(db)


def get_refresh_token_port(db: AsyncSession = Depends(get_db)) -> RefreshTokenPort:
    return RefreshTokenRepository(db)


def get_favorite_port(db: AsyncSession = Depends(get_db)) -> FavoriteRepositoryPort:
    return FavoriteRepository(db)


def get_favorite_port_factory() -> FavoriteRepositoryFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[FavoriteRepositoryPort]:
        async with AsyncSessionLocal() as session:
            yield FavoriteRepository(session)

    return factory


def get_watch_progress_port(
    db: AsyncSession = Depends(get_db),
) -> WatchProgressRepositoryPort:
    return WatchProgressRepository(db)


def get_watch_progress_port_factory() -> WatchProgressRepositoryFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[WatchProgressRepositoryPort]:
        async with AsyncSessionLocal() as session:
            yield WatchProgressRepository(session)

    return factory


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    token_port: RefreshTokenPort = Depends(get_refresh_token_port),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    token = credentials.credentials
    try:
        payload = validate_access_token(token)
    except ExpiredTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        ) from None
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from None

    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )

    try:
        if not isinstance(subject, str):
            raise ValueError("invalid-subject-type")
        user_id = uuid.UUID(subject)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        ) from None

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    session_token = await token_port.get_by_user_id(user_id)
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found"
        )
    if session_token.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked"
        )
    if session_token.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired"
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
    token_port: RefreshTokenPort = Depends(get_refresh_token_port),
) -> User | None:
    if credentials is None:
        return None
    return await get_current_user(
        credentials=credentials, db=db, token_port=token_port
    )


async def get_current_role(
    user: User | None = Depends(get_current_user_optional),
) -> rbac.Role:
    return rbac.resolve_role(user)
