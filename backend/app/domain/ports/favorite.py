from __future__ import annotations

from typing import AsyncContextManager, Callable
from datetime import datetime
import uuid
from typing import Protocol


class FavoriteData(Protocol):
    id: uuid.UUID
    user_id: uuid.UUID
    anime_id: uuid.UUID
    created_at: datetime


class FavoriteRepository(Protocol):
    async def anime_exists(self, anime_id: uuid.UUID) -> bool:
        ...

    async def get(self, user_id: uuid.UUID, anime_id: uuid.UUID) -> FavoriteData | None:
        ...

    async def list(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> list[FavoriteData]:
        ...

    async def add(
        self,
        user_id: uuid.UUID,
        anime_id: uuid.UUID,
        *,
        favorite_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
    ) -> FavoriteData:
        ...

    async def remove(self, user_id: uuid.UUID, anime_id: uuid.UUID) -> bool:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


FavoriteRepositoryFactory = Callable[[], AsyncContextManager[FavoriteRepository]]
