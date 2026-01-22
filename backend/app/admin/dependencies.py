"""
Admin Dependencies - Permission-based dependency injection (STUB ONLY).

This module is a placeholder for future RBAC enforcement logic.
Currently contains no active enforcement - this is by design for Phase 6.

PHASE 6: Permission structure wired, but NO enforcement.
Dependencies exist in endpoint signatures, but return None (noop).

NOTE: No runtime enforcement in this phase. Stub only.
"""
from __future__ import annotations

from typing import Callable

from app.admin.contracts.permissions import AdminPermission


def require_admin_permission(permission: AdminPermission) -> Callable:
    """
    Stub dependency for single admin permission check.
    
    TODO (PHASE 7):
    Enforce admin permission check here.
    - Verify user is authenticated
    - Check user has the required permission
    - Raise HTTPException(403) if unauthorized
    
    Args:
        permission: The required AdminPermission
        
    Returns:
        Dependency function that returns None (noop in PHASE 6)
    """
    async def dependency() -> None:
        # PHASE 6: No enforcement, just structure
        # PHASE 7 will add actual permission checks
        return None
    
    return dependency


def require_admin_permissions(*permissions: AdminPermission) -> Callable:
    """
    Stub dependency for multiple admin permission checks.
    
    TODO (PHASE 7):
    Enforce admin permission checks here.
    - Verify user is authenticated
    - Check user has ALL required permissions
    - Raise HTTPException(403) if unauthorized
    
    Args:
        *permissions: Variable number of required AdminPermissions
        
    Returns:
        Dependency function that returns None (noop in PHASE 6)
    """
    async def dependency() -> None:
        # PHASE 6: No enforcement, just structure
        # PHASE 7 will add actual permission checks
        return None
    
    return dependency
