from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.refresh_token import RefreshToken
from ..domain.ports.token import RefreshTokenPort, RefreshTokenData


async def create_or_rotate_refresh_token(
    session: AsyncSession, user_id: uuid.UUID, token_hash: str, expires_at: datetime
) -> RefreshToken:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    existing = result.scalars().first()
    if existing:
        existing.token_hash = token_hash
        existing.expires_at = expires_at
        existing.revoked = False
        await session.flush()
        return existing

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        revoked=False,
    )
    session.add(refresh_token)
    await session.flush()
    return refresh_token


async def get_refresh_token_by_hash(
    session: AsyncSession, token_hash: str, *, for_update: bool = False
) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    if for_update:
        stmt = stmt.with_for_update()

    result = await session.execute(stmt)
    return result.scalars().first()


async def get_refresh_token_by_user_id(
    session: AsyncSession, user_id: uuid.UUID, *, for_update: bool = False
) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()

    result = await session.execute(stmt)
    return result.scalars().first()


async def revoke_refresh_token(
    session: AsyncSession, user_id: uuid.UUID
) -> RefreshToken | None:
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    token = result.scalars().first()
    if token:
        token.revoked = True
        await session.flush()
    return token


class RefreshTokenRepository(RefreshTokenPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_or_rotate(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshTokenData:
        return await create_or_rotate_refresh_token(
            self._session, user_id, token_hash, expires_at
        )

    async def get_by_hash(
        self, token_hash: str, *, for_update: bool = False
    ) -> RefreshTokenData | None:
        return await get_refresh_token_by_hash(
            self._session, token_hash, for_update=for_update
        )

    async def get_by_user_id(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> RefreshTokenData | None:
        return await get_refresh_token_by_user_id(
            self._session, user_id, for_update=for_update
        )

    async def revoke(self, user_id: uuid.UUID) -> RefreshTokenData | None:
        return await revoke_refresh_token(self._session, user_id)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
