import uuid

from ...background import Job, default_job_runner
from ...domain.ports.favorite import FavoriteRepository, FavoriteRepositoryFactory


async def persist_remove_favorite(
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_repo_factory: FavoriteRepositoryFactory | None = None,
) -> None:
    if favorite_repo_factory is None:
        raise RuntimeError("Favorite repository factory is not configured")
    async with favorite_repo_factory() as favorite_repo:
        try:
            await favorite_repo.remove(user_id, anime_id)
            await favorite_repo.commit()
        except Exception:
            await favorite_repo.rollback()
            raise


_DEFAULT_PERSIST_REMOVE_FAVORITE = persist_remove_favorite


async def remove_favorite(
    favorite_repo: FavoriteRepository,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_repo_factory: FavoriteRepositoryFactory | None = None,
) -> None:
    if (
        favorite_repo_factory is None
        and persist_remove_favorite is _DEFAULT_PERSIST_REMOVE_FAVORITE
    ):
        raise RuntimeError("Favorite repository factory is not configured")

    async def handler() -> None:
        if favorite_repo_factory is None:
            await persist_remove_favorite(user_id, anime_id)
            return
        await persist_remove_favorite(
            user_id, anime_id, favorite_repo_factory=favorite_repo_factory
        )

    job = Job(
        key=f"favorite:remove:{user_id}:{anime_id}",
        handler=handler,
    )
    await default_job_runner.enqueue(job)
