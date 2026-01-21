import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.ports.favorite import FavoriteData, FavoriteRepository as FavoriteRepositoryPort
from ..models.anime import Anime
from ..models.favorite import Favorite


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


async def get_favorite(
    session: AsyncSession, user_id: uuid.UUID, anime_id: uuid.UUID
) -> Favorite | None:
    stmt = select(Favorite).where(
        Favorite.user_id == user_id, Favorite.anime_id == anime_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def add_favorite(
    session: AsyncSession,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> Favorite:
    values = {
        "id": favorite_id or uuid.uuid4(),
        "user_id": user_id,
        "anime_id": anime_id,
    }
    if created_at is not None:
        values["created_at"] = created_at
    insert_fn = _insert_for(session)
    stmt = insert_fn(Favorite).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "anime_id"],
        set_={"created_at": Favorite.created_at},
    )
    await session.execute(stmt)
    favorite = await get_favorite(session, user_id, anime_id)
    if favorite is None:
        raise RuntimeError(
            f"Favorite upsert did not return a row for user={user_id} anime={anime_id}"
        )
    return favorite


async def remove_favorite(
    session: AsyncSession, user_id: uuid.UUID, anime_id: uuid.UUID
) -> bool:
    favorite = await get_favorite(session, user_id, anime_id)
    if favorite is None:
        return False

    session.delete(favorite)
    await session.flush()
    return True


async def list_favorites(
    session: AsyncSession, user_id: uuid.UUID, limit: int, offset: int
) -> list[Favorite]:
    stmt = (
        select(Favorite)
        .where(Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


class FavoriteRepository(FavoriteRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def anime_exists(self, anime_id: uuid.UUID) -> bool:
        return await self._session.get(Anime, anime_id) is not None

    async def get(self, user_id: uuid.UUID, anime_id: uuid.UUID) -> FavoriteData | None:
        return await get_favorite(self._session, user_id, anime_id)

    async def list(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> list[FavoriteData]:
        return await list_favorites(self._session, user_id=user_id, limit=limit, offset=offset)

    async def add(
        self,
        user_id: uuid.UUID,
        anime_id: uuid.UUID,
        *,
        favorite_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
    ) -> FavoriteData:
        return await add_favorite(
            self._session,
            user_id,
            anime_id,
            favorite_id=favorite_id,
            created_at=created_at,
        )

    async def remove(self, user_id: uuid.UUID, anime_id: uuid.UUID) -> bool:
        return await remove_favorite(self._session, user_id, anime_id)

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
