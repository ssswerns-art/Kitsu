"""
Service layer for admin anime management.

This service implements all business logic for anime CMS operations:
- Permission checks via PermissionService
- Lock validation via LockService  
- State transition validation
- Audit logging via AuditService
- Parser protection (manual > parser)
- Automatic broken state detection
"""
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...crud.anime_admin import (
    get_anime_admin_list,
    get_anime_by_id_admin,
    check_anime_has_video,
    detect_anime_errors,
    update_anime_admin,
    auto_update_broken_state,
)
from ...models.user import User
from ...schemas.anime_admin import (
    AnimeAdminListFilter,
    AnimeAdminListItem,
    AnimeAdminDetail,
    AnimeAdminUpdate,
    AnimeAdminUpdateResponse,
    validate_state_transition,
)
from ..admin import PermissionService, LockService
from ..audit import AuditService


class AnimeAdminService:
    """Service for admin anime management operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.permission_service = PermissionService(session)
        self.audit_service = AuditService(session)
    
    async def list_anime(
        self,
        filters: AnimeAdminListFilter,
        actor: User | None = None,
    ) -> tuple[list[AnimeAdminListItem], int]:
        """
        List anime with admin filters.
        
        Requires: anime.view permission
        
        Args:
            filters: Filter and pagination parameters
            actor: User making the request
            
        Returns:
            Tuple of (list of anime items, total count)
            
        Raises:
            HTTPException: If user lacks permission
        """
        # Permission check
        await self.permission_service.require_permission(actor, "anime.view")
        
        # Get anime list from CRUD
        anime_list, total = await get_anime_admin_list(
            self.session,
            state=filters.state,
            source=filters.source,
            has_video=filters.has_video,
            has_errors=filters.has_errors,
            limit=filters.limit,
            offset=filters.offset,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )
        
        # Convert to response schema with computed fields
        items = []
        for anime in anime_list:
            # Compute has_video
            has_video = await check_anime_has_video(self.session, anime.id)
            
            # Compute errors
            errors_count, _ = await detect_anime_errors(self.session, anime)
            
            # Create response item
            item = AnimeAdminListItem(
                id=anime.id,
                title=anime.title,
                poster_url=anime.poster_url,
                state=anime.state,
                source=anime.source,
                year=anime.year,
                status=anime.status,
                is_locked=anime.is_locked,
                locked_fields=anime.locked_fields,
                has_video=has_video,
                errors_count=errors_count,
                created_at=anime.created_at,
                updated_at=anime.updated_at,
                created_by=anime.created_by,
                updated_by=anime.updated_by,
            )
            items.append(item)
        
        return items, total
    
    async def get_anime(
        self,
        anime_id: uuid.UUID,
        actor: User | None = None,
    ) -> AnimeAdminDetail:
        """
        Get anime details for admin.
        
        Requires: anime.view permission
        
        Args:
            anime_id: Anime UUID
            actor: User making the request
            
        Returns:
            Anime detail object
            
        Raises:
            HTTPException: If user lacks permission or anime not found
        """
        # Permission check
        await self.permission_service.require_permission(actor, "anime.view")
        
        # Get anime
        anime = await get_anime_by_id_admin(self.session, anime_id)
        if not anime:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Anime not found"
            )
        
        # Compute fields
        has_video = await check_anime_has_video(self.session, anime.id)
        errors_count, errors = await detect_anime_errors(self.session, anime)
        
        # Create response
        return AnimeAdminDetail(
            id=anime.id,
            title=anime.title,
            title_ru=anime.title_ru,
            title_en=anime.title_en,
            title_original=anime.title_original,
            description=anime.description,
            poster_url=anime.poster_url,
            year=anime.year,
            season=anime.season,
            status=anime.status,
            genres=anime.genres,
            state=anime.state,
            created_by=anime.created_by,
            updated_by=anime.updated_by,
            source=anime.source,
            is_locked=anime.is_locked,
            locked_fields=anime.locked_fields,
            locked_by=anime.locked_by,
            locked_reason=anime.locked_reason,
            locked_at=anime.locked_at,
            is_deleted=anime.is_deleted,
            deleted_at=anime.deleted_at,
            deleted_by=anime.deleted_by,
            delete_reason=anime.delete_reason,
            created_at=anime.created_at,
            updated_at=anime.updated_at,
            has_video=has_video,
            errors_count=errors_count,
            errors=errors,
        )
    
    async def update_anime(
        self,
        anime_id: uuid.UUID,
        update: AnimeAdminUpdate,
        actor: User | None = None,
        actor_type: str = "user",
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AnimeAdminUpdateResponse:
        """
        Update anime with full CMS validation.
        
        Requires: anime.edit permission
        
        Validates:
        - Permission check
        - Lock check  
        - Parser protection (manual > parser)
        - State transition validity
        - Auto-detect broken state
        
        Logs:
        - Audit log (before/after)
        
        Args:
            anime_id: Anime UUID
            update: Update data
            actor: User making the update
            actor_type: Type of actor (user/system)
            ip_address: IP address of requester
            user_agent: User agent of requester
            
        Returns:
            Update response with anime and audit log ID
            
        Raises:
            HTTPException: If validation fails
        """
        # Permission check (outside transaction)
        await self.permission_service.require_permission(actor, "anime.edit")
        
        # All database operations in a single transaction
        async with self.session.begin():
            # Get anime
            anime = await get_anime_by_id_admin(self.session, anime_id)
            if not anime:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Anime not found"
                )
            
            # Check if deleted
            if anime.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="Cannot update deleted anime"
                )
            
            # Get fields to update
            update_dict = update.model_dump(exclude_unset=True, exclude={"reason"})
            fields_to_update = list(update_dict.keys())
            
            if not fields_to_update:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update"
                )
            
            # Lock check
            has_override = await self.permission_service.has_permission(
                actor, "anime.override_lock"
            )
            LockService.check_lock(
                anime,
                fields_to_update,
                actor=actor,
                has_override_permission=has_override,
            )
            
            # Parser protection check
            LockService.check_parser_update(anime, fields_to_update, actor_type)
            
            # State transition validation
            if "state" in update_dict:
                new_state = update_dict["state"]
                if not validate_state_transition(anime.state, new_state):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid state transition from {anime.state} to {new_state}"
                    )
                
                # Additional validation: cannot publish without video
                if new_state == "published":
                    has_video = await check_anime_has_video(self.session, anime.id)
                    if not has_video:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot publish anime without video content"
                        )
            
            # Capture before state for audit
            before_data = LockService.serialize_entity(anime)
            
            # Update anime
            actor_id = actor.id if actor else None
            updated_anime = await update_anime_admin(
                self.session,
                anime,
                update_dict,
                actor_id=actor_id,
            )
            
            # Auto-detect broken state
            warnings = []
            state_changed, reason = await auto_update_broken_state(
                self.session,
                updated_anime,
            )
            if state_changed:
                warnings.append(reason)
            
            # Capture after state for audit
            after_data = LockService.serialize_entity(updated_anime)
            
            # Create audit log
            audit_log = await self.audit_service.log_update(
                entity_type="anime",
                entity_id=anime_id,
                before_data=before_data,
                after_data=after_data,
                actor=actor,
                actor_type=actor_type,
                reason=update.reason,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            
            # Transaction commits here automatically
        
        # Get fresh anime detail (outside transaction)
        anime_detail = await self.get_anime(anime_id, actor)
        
        # Return response with audit log ID
        return AnimeAdminUpdateResponse(
            success=True,
            anime=anime_detail,
            audit_log_id=audit_log.id,
            warnings=warnings,
        )
