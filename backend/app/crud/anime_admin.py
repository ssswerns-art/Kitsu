"""
CRUD operations for admin anime management.

These operations provide data access for the admin interface,
including filtering, sorting, and retrieving anime with computed metadata.
"""
import uuid
from typing import Literal

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.anime import Anime
from ..models.episode import Episode


async def get_anime_admin_list(
    session: AsyncSession,
    state: str | None = None,
    source: str | None = None,
    has_video: bool | None = None,
    has_errors: bool | None = None,
    limit: int = 30,
    offset: int = 0,
    sort_by: Literal["updated_at", "created_at", "title"] = "updated_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> tuple[list[Anime], int]:
    """
    Get anime list for admin with filters and sorting.
    
    Args:
        session: Database session
        state: Filter by state (draft/pending/published/broken/archived)
        source: Filter by source (manual/parser/import)
        has_video: Filter by presence of video content
        has_errors: Filter by presence of errors
        limit: Maximum number of results
        offset: Number of results to skip
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        
    Returns:
        Tuple of (list of anime, total count)
    """
    # Build base query
    query = select(Anime).where(Anime.is_deleted is False)
    
    # Apply filters
    if state:
        query = query.where(Anime.state == state)
    
    if source:
        query = query.where(Anime.source == source)
    
    # Note: has_video and has_errors filtering would require joining with
    # episodes or additional metadata. For now, we'll handle this in the service layer
    # or add computed columns. Keeping the query simple for initial implementation.
    
    # Count total before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply sorting
    if sort_by == "updated_at":
        order_col = Anime.updated_at
    elif sort_by == "created_at":
        order_col = Anime.created_at
    else:  # title
        order_col = Anime.title
    
    if sort_order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    # Execute query
    result = await session.execute(query)
    anime_list = list(result.scalars().all())
    
    return anime_list, total


async def get_anime_by_id_admin(
    session: AsyncSession,
    anime_id: uuid.UUID,
) -> Anime | None:
    """
    Get anime by ID for admin (includes soft-deleted).
    
    Args:
        session: Database session
        anime_id: Anime UUID
        
    Returns:
        Anime if found, None otherwise
    """
    query = select(Anime).where(Anime.id == anime_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def check_anime_has_video(
    session: AsyncSession,
    anime_id: uuid.UUID,
) -> bool:
    """
    Check if anime has at least one episode with video.
    
    An anime has video if there exists at least one episode that:
    - Belongs to a release for this anime
    - Has iframe_url (video source)
    - Is not soft-deleted
    
    Args:
        session: Database session
        anime_id: Anime UUID
        
    Returns:
        True if anime has video, False otherwise
    """
    from ..models.release import Release
    
    # Query: Find any episode with video for this anime
    # Join: Anime -> Release -> Episode
    # Conditions: episode.iframe_url IS NOT NULL AND episode.is_deleted = false
    query = (
        select(func.count())
        .select_from(Episode)
        .join(Release, Episode.release_id == Release.id)
        .where(
            and_(
                Release.anime_id == anime_id,
                Episode.iframe_url.isnot(None),
                Episode.iframe_url != "",
                Episode.is_deleted is False,
            )
        )
    )
    
    result = await session.execute(query)
    count = result.scalar() or 0
    return count > 0


async def detect_anime_errors(
    session: AsyncSession,
    anime: Anime,
) -> tuple[int, list[str]]:
    """
    Detect errors/issues with anime.
    
    Args:
        session: Database session
        anime: Anime object
        
    Returns:
        Tuple of (error_count, list_of_error_messages)
    """
    errors = []
    
    # Check for missing critical fields
    if not anime.title:
        errors.append("Missing title")
    
    if not anime.description:
        errors.append("Missing description")
    
    if not anime.poster_url:
        errors.append("Missing poster")
    
    # Check for video availability
    has_video = await check_anime_has_video(session, anime.id)
    if not has_video:
        errors.append("No video content available")
    
    # Check state consistency
    if anime.state == "published" and not has_video:
        errors.append("Published anime must have video content")
    
    return len(errors), errors


async def update_anime_admin(
    session: AsyncSession,
    anime: Anime,
    update_data: dict,
    actor_id: uuid.UUID | None = None,
) -> Anime:
    """
    Update anime with admin data.
    
    Note: This only updates the model fields. Validation, permissions,
    and audit logging are handled in the service layer.
    
    Args:
        session: Database session
        anime: Anime object to update
        update_data: Dictionary of fields to update
        actor_id: ID of user making the update
        
    Returns:
        Updated anime object
    """
    # Update only non-None fields
    for field, value in update_data.items():
        if hasattr(anime, field):
            # Only update if value is different from current value
            current_value = getattr(anime, field)
            if value != current_value:
                setattr(anime, field, value)
    
    # Set updated_by
    if actor_id:
        anime.updated_by = actor_id
    
    # Mark as manual if edited by user
    if actor_id and anime.source != "manual":
        anime.source = "manual"
    
    # Commit changes
    session.add(anime)
    await session.flush()
    await session.refresh(anime)
    
    return anime


async def auto_update_broken_state(
    session: AsyncSession,
    anime: Anime,
) -> tuple[bool, str | None]:
    """
    Automatically update anime state to 'broken' if it has errors.
    
    Args:
        session: Database session
        anime: Anime object
        
    Returns:
        Tuple of (state_changed, reason)
    """
    errors_count, errors = await detect_anime_errors(session, anime)
    
    # If anime has errors and is not already broken/draft, mark as broken
    if errors_count > 0 and anime.state not in ["broken", "draft", "archived"]:
        anime.state = "broken"
        reason = f"Auto-marked as broken: {', '.join(errors)}"
        session.add(anime)
        await session.flush()
        return True, reason
    
    return False, None
