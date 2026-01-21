import logging
import uuid
from datetime import datetime, timezone

from ...background import Job, default_job_runner
from ...domain.invariants import (
    InvariantViolation,
    validate_forward_only_episode,
    validate_forward_only_progress,
    validate_position_bounds,
    validate_progress_bounds,
    validate_referential_integrity_anime,
)
from ...domain.ports.watch_progress import (
    WatchProgressData,
    WatchProgressRepository,
    WatchProgressRepositoryFactory,
)
from ...errors import NotFoundError, ValidationError
from ...schemas.watch import WatchProgressRead

logger = logging.getLogger(__name__)


def _validate_update_request(
    episode: int, position_seconds: int | None, progress_percent: float | None
) -> None:
    if episode <= 0:
        raise ValidationError("Episode number must be positive")
    if position_seconds is None and progress_percent is None:
        raise ValidationError("Either position_seconds or progress_percent must be provided")
    if progress_percent is not None and not (0 <= progress_percent <= 100):
        raise ValidationError("Progress percent must be between 0 and 100")
    if position_seconds is not None and position_seconds < 0:
        raise ValidationError("Position in seconds must be non-negative")


async def get_anime_by_id(
    watch_repo: WatchProgressRepository, anime_id: uuid.UUID
) -> bool:
    return await watch_repo.anime_exists(anime_id)


async def get_watch_progress(
    watch_repo: WatchProgressRepository, user_id: uuid.UUID, anime_id: uuid.UUID
) -> WatchProgressData | None:
    return await watch_repo.get(user_id, anime_id)


async def _apply_watch_progress(
    watch_repo: WatchProgressRepository,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    episode: int,
    position_seconds: int | None,
    progress_percent: float | None,
    *,
    progress_id: uuid.UUID,
    created_at: datetime,
    last_watched_at: datetime,
) -> None:
    """
    Apply watch progress update with exactly-once semantics and domain invariants.
    
    IDEMPOTENCY KEY: (user_id, anime_id)
    INVARIANT: Repeated execution either applies effect OR skips deterministically.
    
    DOMAIN INVARIANTS ENFORCED:
    - INVARIANT-2: Forward-only episode (cannot decrease episode number)
    - INVARIANT-2: Forward-only progress (cannot decrease progress within same episode)
    - INVARIANT-2: Valid bounds (progress 0-100, position >= 0)
    - INVARIANT-3: Referential integrity (anime must exist)
    """
    # INVARIANT-3: Referential integrity - anime must exist
    anime_exists = await get_anime_by_id(watch_repo, anime_id)
    validate_referential_integrity_anime(
        anime_exists,
        anime_id=anime_id,
        operation="update watch progress",
    )

    # INVARIANT-2: Validate bounds
    validate_progress_bounds(progress_percent)
    validate_position_bounds(position_seconds)

    # IDEMPOTENCY CHECK: Get current state before applying effect
    progress = await get_watch_progress(watch_repo, user_id, anime_id)
    
    if progress:
        # Check if this exact update was already applied
        if (
            progress.episode == episode
            and progress.position_seconds == position_seconds
            and progress.progress_percent == progress_percent
        ):
            # Effect already applied - idempotent skip
            logger.info(
                "idempotent_skip operation=watch-progress user_id=%s anime_id=%s episode=%d "
                "reason=exact_match_exists",
                user_id,
                anime_id,
                episode,
            )
            return
        
        # INVARIANT-2: Forward-only state checks
        validate_forward_only_episode(
            progress.episode,
            episode,
            user_id=user_id,
            anime_id=anime_id,
        )
        validate_forward_only_progress(
            progress.episode,
            progress.progress_percent,
            episode,
            progress_percent,
            user_id=user_id,
            anime_id=anime_id,
        )
        
        # Update existing progress (idempotent via unique constraint)
        await watch_repo.update(
            progress,
            episode,
            position_seconds,
            progress_percent,
            last_watched_at=last_watched_at,
        )
        logger.info(
            "operation=watch-progress action=update user_id=%s anime_id=%s episode=%d",
            user_id,
            anime_id,
            episode,
        )
    else:
        # Create new progress (idempotent via unique constraint on user_id, anime_id)
        await watch_repo.add(
            user_id,
            anime_id,
            episode,
            position_seconds,
            progress_percent,
            progress_id=progress_id,
            created_at=created_at,
            last_watched_at=last_watched_at,
        )
        logger.info(
            "operation=watch-progress action=create user_id=%s anime_id=%s episode=%d",
            user_id,
            anime_id,
            episode,
        )


async def persist_update_progress(
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    episode: int,
    position_seconds: int | None,
    progress_percent: float | None,
    *,
    progress_id: uuid.UUID,
    created_at: datetime,
    last_watched_at: datetime,
    watch_repo_factory: WatchProgressRepositoryFactory | None = None,
) -> None:
    if watch_repo_factory is None:
        raise RuntimeError("Watch progress repository factory is not configured")
    async with watch_repo_factory() as watch_repo:
        await _apply_watch_progress(
            watch_repo,
            user_id,
            anime_id,
            episode,
            position_seconds,
            progress_percent,
            progress_id=progress_id,
            created_at=created_at,
            last_watched_at=last_watched_at,
        )


_DEFAULT_PERSIST_UPDATE_PROGRESS = persist_update_progress


async def update_progress(
    watch_repo: WatchProgressRepository,
    user_id: uuid.UUID,
    anime_id: uuid.UUID,
    episode: int,
    position_seconds: int | None = None,
    progress_percent: float | None = None,
    watch_repo_factory: WatchProgressRepositoryFactory | None = None,
) -> WatchProgressRead:
    _validate_update_request(episode, position_seconds, progress_percent)

    anime_exists = await get_anime_by_id(watch_repo, anime_id)
    if not anime_exists:
        raise NotFoundError("Anime not found")

    existing_progress = await get_watch_progress(watch_repo, user_id, anime_id)
    now = datetime.now(timezone.utc)
    progress_id = existing_progress.id if existing_progress else uuid.uuid4()
    created_at = existing_progress.created_at if existing_progress else now

    result = WatchProgressRead(
        id=progress_id,
        anime_id=anime_id,
        episode=episode,
        position_seconds=position_seconds,
        progress_percent=progress_percent,
        created_at=created_at,
        last_watched_at=now,
    )

    if (
        watch_repo_factory is None
        and persist_update_progress is _DEFAULT_PERSIST_UPDATE_PROGRESS
    ):
        raise RuntimeError("Watch progress repository factory is not configured")

    async def handler() -> None:
        if watch_repo_factory is None:
            await persist_update_progress(
                user_id,
                anime_id,
                episode,
                position_seconds,
                progress_percent,
                progress_id=progress_id,
                created_at=created_at,
                last_watched_at=result.last_watched_at,
            )
            return
        await persist_update_progress(
            user_id,
            anime_id,
            episode,
            position_seconds,
            progress_percent,
            progress_id=progress_id,
            created_at=created_at,
            last_watched_at=result.last_watched_at,
            watch_repo_factory=watch_repo_factory,
        )

    job = Job(
        key=(
            f"watch-progress:{user_id}:{anime_id}:episode={episode}:"
            f"position={position_seconds if position_seconds is not None else 'none'}:"
            f"percent={progress_percent if progress_percent is not None else 'none'}"
        ),
        handler=handler,
    )
    await default_job_runner.enqueue(job)
    return result
