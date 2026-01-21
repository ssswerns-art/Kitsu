import logging
import uuid

from ...background import Job, default_job_runner
from ...domain.ports.favorite import FavoriteRepository, FavoriteRepositoryFactory

logger = logging.getLogger(__name__)


async def persist_remove_favorite(
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    favorite_repo_factory: FavoriteRepositoryFactory | None = None,
) -> None:
    """
    Persist favorite removal with exactly-once semantics.
    
    IDEMPOTENCY KEY: (user_id, anime_id)
    INVARIANT: Repeated execution is safe - either removes OR skips if not exists.
    """
    if favorite_repo_factory is None:
        raise RuntimeError("Favorite repository factory is not configured")
    async with favorite_repo_factory() as favorite_repo:
        try:
            # IDEMPOTENCY CHECK: Check if favorite exists before removal
            existing = await favorite_repo.get(user_id, anime_id)
            if existing is None:
                # Effect already applied (favorite doesn't exist) - idempotent skip
                logger.info(
                    "idempotent_skip operation=favorite:remove user_id=%s anime_id=%s "
                    "reason=not_found",
                    user_id,
                    anime_id,
                )
                await favorite_repo.commit()
                return
            
            # Effect not yet applied - apply removal atomically
            removed = await favorite_repo.remove(user_id, anime_id)
            await favorite_repo.commit()
            
            if removed:
                logger.info(
                    "operation=favorite:remove action=delete user_id=%s anime_id=%s",
                    user_id,
                    anime_id,
                )
            else:
                # Race condition - another process removed it between check and delete
                logger.info(
                    "idempotent_skip operation=favorite:remove user_id=%s anime_id=%s "
                    "reason=concurrent_removal",
                    user_id,
                    anime_id,
                )
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
