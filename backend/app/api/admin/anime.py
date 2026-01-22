"""
Admin API endpoints for anime management.

These endpoints provide CMS-level anime management with:
- Permission checks (anime.view, anime.edit)
- Audit logging
- Lock mechanism validation
- State transition validation
- Parser protection
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...dependencies import get_db, get_current_user
from ...models.user import User
from ...schemas.anime_admin import (
    AnimeAdminListFilter,
    AnimeAdminDetail,
    AnimeAdminUpdate,
    AnimeAdminUpdateResponse,
)
from ...services.admin.anime_service import AnimeAdminService


router = APIRouter(prefix="/admin/anime", tags=["admin-anime"])


@router.get("/", response_model=dict)
async def list_anime(
    state: str | None = Query(None, description="Filter by state"),
    source: str | None = Query(None, description="Filter by source"),
    has_video: bool | None = Query(None, description="Filter by video presence"),
    has_errors: bool | None = Query(None, description="Filter by errors presence"),
    limit: int = Query(30, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sort_by: str = Query("updated_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List anime with admin filters.
    
    Requires: anime.view permission
    
    Returns paginated list of anime with metadata for admin interface.
    """
    # Create filter object
    filters = AnimeAdminListFilter(
        state=state,
        source=source,
        has_video=has_video,
        has_errors=has_errors,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    # Get service
    service = AnimeAdminService(db)
    
    # List anime
    items, total = await service.list_anime(filters, actor=current_user)
    
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{anime_id}", response_model=AnimeAdminDetail)
async def get_anime(
    anime_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get anime details for admin.
    
    Requires: anime.view permission
    
    Returns full anime details with computed fields (has_video, errors).
    """
    service = AnimeAdminService(db)
    return await service.get_anime(anime_id, actor=current_user)


@router.patch("/{anime_id}", response_model=AnimeAdminUpdateResponse)
async def update_anime(
    anime_id: UUID,
    update: AnimeAdminUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update anime with CMS validation.
    
    Requires: anime.edit permission
    
    Validates:
    - Permission check
    - Lock check
    - Parser protection (manual > parser)
    - State transition validity
    
    Automatically:
    - Sets source="manual" for user edits
    - Detects and marks broken state
    - Creates audit log
    
    Returns updated anime with audit log reference.
    """
    service = AnimeAdminService(db)
    
    # Get client IP and user agent for audit
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    return await service.update_anime(
        anime_id=anime_id,
        update=update,
        actor=current_user,
        actor_type="user",
        ip_address=ip_address,
        user_agent=user_agent,
    )
