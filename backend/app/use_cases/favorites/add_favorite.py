import uuid
from datetime import datetime, timezone

from ...background import Job, default_job_runner
from ...domain.ports.favorite import (
    FavoriteData,
    FavoriteRepository,
    FavoriteRepositoryFactory,
)
from ...errors import ConflictError, NotFoundError
from ...schemas.favorite import FavoriteRead

async def get_anime_by_id(
    favorite_repo: FavoriteRepository, anime_id: uuid.UUID
) -> bool:
    return await favorite_repo.anime_exists(anime_id)

async def get_favorite(
    favorite_repo: FavoriteRepository, user_id: uuid.UUID, anime_id: uuid.UUID
) -> FavoriteData | None:
    return await favorite_repo.get(user_id, anime_id)


def _favorite_id_for(user_id: uuid.UUID, anime_id: uuid.UUID) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"kitsu.favorite:{user_id}:{anime_id}")


async def _apply_add_favorite(
    favorite_repo: FavoriteRepository,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_id: uuid.UUID,
    created_at: datetime,
) -> None:
    try:
        anime_exists = await get_anime_by_id(favorite_repo, anime_id)
        if not anime_exists:
            raise NotFoundError("Anime not found")

        existing = await get_favorite(favorite_repo, user_id, anime_id)
        if existing is None:
            await favorite_repo.add(
                user_id,
                anime_id,
                favorite_id=favorite_id,
                created_at=created_at,
            )
        await favorite_repo.commit()
    except Exception:
        await favorite_repo.rollback()
        raise


async def persist_add_favorite(
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_id: uuid.UUID,
    created_at: datetime,
    favorite_repo_factory: FavoriteRepositoryFactory | None = None,
) -> None:
    if favorite_repo_factory is None:
        raise RuntimeError("Favorite repository factory is not configured")
    async with favorite_repo_factory() as favorite_repo:
        await _apply_add_favorite(
            favorite_repo, user_id, anime_id, favorite_id, created_at
        )


_DEFAULT_PERSIST_ADD_FAVORITE = persist_add_favorite


async def add_favorite(
    favorite_repo: FavoriteRepository,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_repo_factory: FavoriteRepositoryFactory | None = None,
) -> FavoriteRead:
    anime_exists = await get_anime_by_id(favorite_repo, anime_id)
    if not anime_exists:
        raise NotFoundError("Anime not found")

    existing = await get_favorite(favorite_repo, user_id, anime_id)
    if existing:
        raise ConflictError("Favorite already exists")

    favorite_id = _favorite_id_for(user_id, anime_id)
    created_at = datetime.now(timezone.utc)
    result = FavoriteRead(id=favorite_id, anime_id=anime_id, created_at=created_at)

    if (
        favorite_repo_factory is None
        and persist_add_favorite is _DEFAULT_PERSIST_ADD_FAVORITE
    ):
        raise RuntimeError("Favorite repository factory is not configured")

    async def handler() -> None:
        if favorite_repo_factory is None:
            await persist_add_favorite(user_id, anime_id, favorite_id, created_at)
            return
        await persist_add_favorite(
            user_id,
            anime_id,
            favorite_id,
            created_at,
            favorite_repo_factory=favorite_repo_factory,
        )

    job = Job(key=f"favorite:add:{user_id}:{anime_id}", handler=handler)
    await default_job_runner.enqueue(job)
    return result
