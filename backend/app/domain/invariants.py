"""
Domain invariants module.

This module defines and enforces domain-level invariants to prevent data drift.
All invariants are checked BEFORE any side effects (database writes).

INVARIANTS:
1. Single Source of Truth - No duplicate fields with same meaning
2. Forward-only state - Some state transitions cannot go backwards
3. Referential consistency - No orphaned entities
4. Domain > API > Background - All checks in domain layer
5. Explicit rejection - Clear errors, no silent failures
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InvariantViolation(Exception):
    """
    Raised when a domain invariant is violated.
    
    This is a domain-level error that should be handled explicitly,
    never silently ignored.
    """
    
    def __init__(self, message: str, *, invariant: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.invariant = invariant
        self.details = details or {}
        
        # Log invariant violation
        logger.error(
            "invariant_violation invariant=%s message=%s details=%s",
            invariant,
            message,
            details,
        )


def validate_forward_only_episode(
    current_episode: int | None,
    new_episode: int,
    *,
    user_id: Any,
    anime_id: Any,
) -> None:
    """
    INVARIANT-2: Forward-only state for episode number.
    
    Episode number can only increase or stay the same, never decrease.
    Allows rewatching same episode but prevents accidental rollback.
    
    Args:
        current_episode: Current episode number (None if first time)
        new_episode: New episode number to set
        user_id: User ID for logging
        anime_id: Anime ID for logging
        
    Raises:
        InvariantViolation: If new_episode < current_episode
    """
    if current_episode is not None and new_episode < current_episode:
        raise InvariantViolation(
            f"Cannot decrease episode number from {current_episode} to {new_episode}",
            invariant="INVARIANT-2.episode_forward_only",
            details={
                "user_id": str(user_id),
                "anime_id": str(anime_id),
                "current_episode": current_episode,
                "new_episode": new_episode,
            },
        )


def validate_forward_only_progress(
    current_episode: int | None,
    current_progress: float | None,
    new_episode: int,
    new_progress: float | None,
    *,
    user_id: Any,
    anime_id: Any,
) -> None:
    """
    INVARIANT-2: Forward-only state for progress percentage.
    
    Progress percent can only increase within same episode.
    Resets to new value when moving to different episode.
    
    Args:
        current_episode: Current episode number
        current_progress: Current progress percentage
        new_episode: New episode number
        new_progress: New progress percentage
        user_id: User ID for logging
        anime_id: Anime ID for logging
        
    Raises:
        InvariantViolation: If progress decreases within same episode
    """
    # Progress can reset when changing episodes
    if current_episode is None or new_episode != current_episode:
        return
    
    # Within same episode, progress should not decrease
    if current_progress is not None and new_progress is not None:
        if new_progress < current_progress:
            raise InvariantViolation(
                f"Cannot decrease progress from {current_progress}% to {new_progress}% within same episode",
                invariant="INVARIANT-2.progress_forward_only",
                details={
                    "user_id": str(user_id),
                    "anime_id": str(anime_id),
                    "episode": new_episode,
                    "current_progress": current_progress,
                    "new_progress": new_progress,
                },
            )


def validate_progress_bounds(progress_percent: float | None) -> None:
    """
    INVARIANT-2: Progress percentage must be within valid bounds.
    
    Args:
        progress_percent: Progress percentage to validate
        
    Raises:
        InvariantViolation: If progress is outside [0, 100] range
    """
    if progress_percent is not None:
        if not (0 <= progress_percent <= 100):
            raise InvariantViolation(
                f"Progress percent {progress_percent} must be between 0 and 100",
                invariant="INVARIANT-2.progress_bounds",
                details={"progress_percent": progress_percent},
            )


def validate_position_bounds(position_seconds: int | None) -> None:
    """
    INVARIANT-2: Position in seconds must be non-negative.
    
    Args:
        position_seconds: Position in seconds to validate
        
    Raises:
        InvariantViolation: If position is negative
    """
    if position_seconds is not None:
        if position_seconds < 0:
            raise InvariantViolation(
                f"Position {position_seconds} seconds must be non-negative",
                invariant="INVARIANT-2.position_bounds",
                details={"position_seconds": position_seconds},
            )


def validate_referential_integrity_anime(
    anime_exists: bool,
    *,
    anime_id: Any,
    operation: str,
) -> None:
    """
    INVARIANT-3: Referential consistency for anime.
    
    Cannot create favorite/watch_progress for non-existent anime.
    
    Args:
        anime_exists: Whether the anime exists
        anime_id: Anime ID for logging
        operation: Operation being performed (for error message)
        
    Raises:
        InvariantViolation: If anime doesn't exist
    """
    if not anime_exists:
        raise InvariantViolation(
            f"Cannot {operation}: anime not found",
            invariant="INVARIANT-3.anime_referential_integrity",
            details={
                "anime_id": str(anime_id),
                "operation": operation,
            },
        )


def log_invariant_skip(
    invariant: str,
    reason: str,
    **kwargs: Any,
) -> None:
    """
    INVARIANT-5: Log when operation skipped due to invariant.
    
    Args:
        invariant: Invariant name
        reason: Reason for skip
        **kwargs: Additional context
    """
    logger.info(
        "invariant_skip invariant=%s reason=%s %s",
        invariant,
        reason,
        " ".join(f"{k}={v}" for k, v in kwargs.items()),
    )
