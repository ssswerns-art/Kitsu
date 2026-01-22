"""
Admin Dependencies - Permission-based dependency injection with RBAC enforcement.

PHASE 7: Real RBAC enforcement active.
All admin endpoints now verify user authentication and permissions.

SECURITY: All permission checks enforce:
- User must be authenticated
- User must be admin actor (not system/bot)
- User must have explicit permissions
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.contracts.permissions import AdminPermission
from app.crud.audit_log import AuditLogRepository
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.admin.permission_service import PermissionService


def require_admin_permission(permission: AdminPermission) -> Callable:
    """
    Enforce admin permission check for a single permission.
    
    Verifies:
    - User is authenticated (401 if not)
    - User is admin actor (not system/bot)
    - User has the required permission (403 if not)
    
    AUDIT ISSUE #8: Logs permission denials to audit_logs table.
    
    Args:
        permission: The required AdminPermission
        
    Returns:
        Dependency function that enforces the permission check
    """
    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        permission_service = PermissionService(db)
        
        # Check if user has the required permission
        # PermissionService.has_permission handles all security checks
        has_perm = await permission_service.has_permission(
            user=user,
            permission_name=permission.value,
            actor_type="user"
        )
        
        if not has_perm:
            # AUDIT ISSUE #8: Log permission denial (best-effort, fire-and-forget)
            try:
                audit_repo = AuditLogRepository(db)
                await audit_repo.create(
                    actor_id=user.id,
                    actor_type="user",
                    action="permission_denied",
                    entity_type="admin_permission",
                    entity_id=permission.value,
                    reason="RBAC_DENIED",
                    before=None,
                    after={
                        "required_permissions": [permission.value],
                        "request_method": request.method,
                        "request_path": request.url.path,
                    },
                )
            except Exception:
                # CRITICAL: Audit logging failures MUST NOT block the 403 response
                # Silently continue - the denial will still be enforced
                pass
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value} required"
            )
    
    return dependency


def require_admin_permissions(*permissions: AdminPermission) -> Callable:
    """
    Enforce admin permission checks for multiple permissions.
    
    Verifies:
    - User is authenticated (401 if not)
    - User is admin actor (not system/bot)
    - User has ALL required permissions (403 if not)
    
    AUDIT ISSUE #8: Logs permission denials to audit_logs table.
    
    Args:
        *permissions: Variable number of required AdminPermissions
        
    Returns:
        Dependency function that enforces all permission checks
    """
    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        permission_service = PermissionService(db)
        
        # Check if user has all required permissions
        permission_names = [perm.value for perm in permissions]
        has_all = await permission_service.has_all_permissions(
            user=user,
            permission_names=permission_names,
            actor_type="user"
        )
        
        if not has_all:
            # AUDIT ISSUE #8: Log permission denial (best-effort, fire-and-forget)
            try:
                audit_repo = AuditLogRepository(db)
                await audit_repo.create(
                    actor_id=user.id,
                    actor_type="user",
                    action="permission_denied",
                    entity_type="admin_permission",
                    entity_id=",".join(permission_names),
                    reason="RBAC_DENIED",
                    before=None,
                    after={
                        "required_permissions": permission_names,
                        "request_method": request.method,
                        "request_path": request.url.path,
                    },
                )
            except Exception:
                # CRITICAL: Audit logging failures MUST NOT block the 403 response
                # Silently continue - the denial will still be enforced
                pass
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires all of {permission_names}"
            )
    
    return dependency
