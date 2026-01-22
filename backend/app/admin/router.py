"""
Centralized Admin Router - READ and WRITE endpoints.

PHASE 6: READ-ONLY admin API with permissions wired (NO enforcement).
All endpoints return mock data without database access.
Permission dependencies are present but do not enforce access control.

PHASE 7: RBAC enforcement enabled. All endpoints verify permissions.

PHASE 8: WRITE endpoints added with audit logging.
- POST /admin/users/{user_id}/roles - Update user roles
- POST /admin/roles/assign - Bulk role assignment
All write actions are audited with fire-and-forget logging.

PHASE 9: Parser/System write actions added.
- POST /admin/parser/restart - Restart parser (stub)
- POST /admin/parser/sync - Manual sync trigger (stub)
- POST /admin/system/maintenance - Toggle maintenance mode (stub)
All write actions are audited with fire-and-forget logging.

NOTE: Write endpoints are stubs with TODO comments for DB logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.admin.contracts.parser import ParserStatusRead, ParserJobStatusRead
from app.admin.contracts.permissions import AdminPermission
from app.admin.contracts.roles import AdminRoleList, AdminRoleRead
from app.admin.contracts.system import SystemHealthRead, SystemComponentStatus
from app.admin.contracts.users import AdminUserList, AdminUserRead, AdminUserShort
from app.admin.dependencies import require_admin_permission
from app.admin.services.audit_service import AuditService
from app.dependencies import get_current_user
from app.models.user import User

# Create admin router with READ-ONLY endpoints
router = APIRouter(
    prefix="/admin",
    tags=["admin-core"],
)


@router.get("/users", response_model=AdminUserList)
async def list_users(
    _: None = Depends(require_admin_permission(AdminPermission.USERS_VIEW)),
) -> AdminUserList:
    """
    List all users (READ-ONLY, mock data).
    
    Returns paginated list of users with mock data.
    No database access, no RBAC enforcement (PHASE 6).
    
    Required permission: USERS_VIEW (wired but not enforced)
    """
    # Mock data - no database access
    mock_users = [
        AdminUserShort(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="admin@example.com",
            is_active=True,
        ),
        AdminUserShort(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            email="user@example.com",
            is_active=True,
        ),
    ]
    
    return AdminUserList(
        users=mock_users,
        total=len(mock_users),
        page=1,
        page_size=10,
    )


@router.get("/users/{user_id}", response_model=AdminUserRead)
async def get_user(
    user_id: UUID,
    _: None = Depends(require_admin_permission(AdminPermission.USERS_VIEW)),
) -> AdminUserRead:
    """
    Get user details (READ-ONLY, mock data).
    
    Returns complete user information with mock data.
    No database access, no RBAC enforcement (PHASE 6).
    
    Required permission: USERS_VIEW (wired but not enforced)
    """
    # Mock data - no database access
    return AdminUserRead(
        id=user_id,
        email="admin@example.com",
        is_active=True,
        roles=["admin", "moderator"],
        created_at=datetime.now(timezone.utc),
        last_login_at=datetime.now(timezone.utc),
    )


@router.get("/roles", response_model=AdminRoleList)
async def list_roles(
    _: None = Depends(require_admin_permission(AdminPermission.ROLES_VIEW)),
) -> AdminRoleList:
    """
    List all roles (READ-ONLY, mock data).
    
    Returns list of roles with mock data.
    No database access, no RBAC enforcement (PHASE 6).
    
    Required permission: ROLES_VIEW (wired but not enforced)
    """
    # Mock data - no database access
    mock_roles = [
        AdminRoleRead(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            name="admin",
            display_name="Administrator",
            permissions=["admin.users.view", "admin.users.manage"],
            is_system=True,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        ),
        AdminRoleRead(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            name="moderator",
            display_name="Moderator",
            permissions=["admin.users.view"],
            is_system=False,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        ),
    ]
    
    return AdminRoleList(
        roles=mock_roles,
        total=len(mock_roles),
    )


@router.get("/permissions", response_model=list[AdminPermission])
async def list_permissions(
    _: None = Depends(require_admin_permission(AdminPermission.ROLES_VIEW)),
) -> list[AdminPermission]:
    """
    List all permissions (READ-ONLY, mock data).
    
    Returns list of all available admin permissions.
    No database access, no RBAC enforcement (PHASE 6).
    
    Required permission: ROLES_VIEW (wired but not enforced)
    """
    # Return all available permissions from enum
    return list(AdminPermission)


@router.get("/parser/status", response_model=ParserStatusRead)
async def get_parser_status(
    _: None = Depends(require_admin_permission(AdminPermission.PARSER_VIEW)),
) -> ParserStatusRead:
    """
    Get parser status (READ-ONLY, mock data).
    
    Returns parser system status with mock data.
    No database access, no RBAC enforcement (PHASE 6).
    
    Required permission: PARSER_VIEW (wired but not enforced)
    """
    # Mock data - no database access
    mock_jobs = [
        ParserJobStatusRead(
            job_name="anime_scraper",
            state="idle",
            last_run_at=datetime.now(timezone.utc),
            next_run_at=None,
            last_duration_ms=1500,
            error=None,
        ),
        ParserJobStatusRead(
            job_name="metadata_updater",
            state="success",
            last_run_at=datetime.now(timezone.utc),
            next_run_at=None,
            last_duration_ms=2300,
            error=None,
        ),
    ]
    
    return ParserStatusRead(
        is_enabled=True,
        is_healthy=True,
        jobs=mock_jobs,
        last_check_at=datetime.now(timezone.utc),
    )


@router.get("/system/health", response_model=SystemHealthRead)
async def get_system_health() -> SystemHealthRead:
    """
    Get system health (READ-ONLY, mock data).
    
    Returns system health status with mock data.
    No database access, no RBAC enforcement (PHASE 6).
    
    NOTE: No permission required - system health monitoring endpoint.
    """
    # Mock data - no database access
    mock_components = [
        SystemComponentStatus(
            name="database",
            status="healthy",
            response_time_ms=15,
            error=None,
            details={"connection_pool": "active"},
        ),
        SystemComponentStatus(
            name="redis",
            status="healthy",
            response_time_ms=5,
            error=None,
            details=None,
        ),
        SystemComponentStatus(
            name="parser",
            status="healthy",
            response_time_ms=10,
            error=None,
            details=None,
        ),
    ]
    
    return SystemHealthRead(
        status="healthy",
        components=mock_components,
        checked_at=datetime.now(timezone.utc),
    )


# ============================================================================
# PHASE 8: WRITE ENDPOINTS (MINIMAL)
# ============================================================================


class UpdateUserRolesRequest(BaseModel):
    """Request body for updating user roles."""
    roles: list[str]


class AssignRolesRequest(BaseModel):
    """Request body for bulk role assignment."""
    user_id: UUID
    roles: list[str]


@router.post("/users/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def update_user_roles(
    user_id: UUID,
    request: UpdateUserRolesRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(require_admin_permission(AdminPermission.USERS_MANAGE)),
) -> Response:
    """
    Update user roles (WRITE, stub implementation).
    
    PHASE 8: Minimal write endpoint with audit logging.
    No real database logic - TODO stub only.
    Audit logging is fire-and-forget and won't block the request.
    
    Required permission: USERS_MANAGE
    
    Args:
        user_id: UUID of the user to update
        request: List of role names to assign
        user: Current authenticated user (for audit)
    
    Returns:
        204 No Content on success
    """
    # TODO: Implement actual database logic to update user roles
    # For now, this is a stub endpoint that only logs the action
    
    # Audit logging - fire-and-forget, AFTER successful RBAC check
    audit_service = AuditService()
    await audit_service.log_admin_action(
        actor_id=user.id,
        action="admin.users.roles.update",
        target_type="user",
        target_id=user_id,
        payload={"roles": request.roles},
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/roles/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_roles_bulk(
    request: AssignRolesRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(require_admin_permission(AdminPermission.ROLES_MANAGE)),
) -> Response:
    """
    Assign roles in bulk (WRITE, stub implementation).
    
    PHASE 8: Minimal write endpoint with audit logging.
    No real database logic - TODO stub only.
    Audit logging is fire-and-forget and won't block the request.
    
    Required permission: ROLES_MANAGE
    
    Args:
        request: User ID and list of role names to assign
        user: Current authenticated user (for audit)
    
    Returns:
        204 No Content on success
    """
    # TODO: Implement actual database logic for bulk role assignment
    # For now, this is a stub endpoint that only logs the action
    
    # Audit logging - fire-and-forget, AFTER successful RBAC check
    audit_service = AuditService()
    await audit_service.log_admin_action(
        actor_id=user.id,
        action="admin.roles.assign",
        target_type="user",
        target_id=request.user_id,
        payload={"roles": request.roles},
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# PHASE 9: PARSER / SYSTEM WRITE ENDPOINTS (MINIMAL)
# ============================================================================


@router.post("/parser/restart", status_code=status.HTTP_204_NO_CONTENT)
async def restart_parser(
    user: User = Depends(get_current_user),
    _: None = Depends(require_admin_permission(AdminPermission.PARSER_MANAGE)),
) -> Response:
    """
    Restart parser system (WRITE, stub implementation).
    
    PHASE 9: Minimal write endpoint with audit logging.
    No real restart logic - TODO stub only.
    Audit logging is fire-and-forget and won't block the request.
    
    Required permission: PARSER_MANAGE
    
    Args:
        user: Current authenticated user (for audit)
    
    Returns:
        204 No Content on success
    """
    # TODO: Implement actual parser restart logic
    # For now, this is a stub endpoint that only logs the action
    
    # Audit logging - fire-and-forget, AFTER successful RBAC check
    audit_service = AuditService()
    await audit_service.log_admin_action(
        actor_id=user.id,
        action="admin.parser.restart",
        target_type="system",
        target_id="parser",
        payload={},
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/parser/sync", status_code=status.HTTP_204_NO_CONTENT)
async def sync_parser(
    user: User = Depends(get_current_user),
    _: None = Depends(require_admin_permission(AdminPermission.PARSER_MANAGE)),
) -> Response:
    """
    Trigger manual parser sync (WRITE, stub implementation).
    
    PHASE 9: Minimal write endpoint with audit logging.
    No real sync trigger logic - TODO stub only.
    Audit logging is fire-and-forget and won't block the request.
    
    Required permission: PARSER_MANAGE
    
    Args:
        user: Current authenticated user (for audit)
    
    Returns:
        204 No Content on success
    """
    # TODO: Implement actual parser sync trigger logic
    # For now, this is a stub endpoint that only logs the action
    
    # Audit logging - fire-and-forget, AFTER successful RBAC check
    audit_service = AuditService()
    await audit_service.log_admin_action(
        actor_id=user.id,
        action="admin.parser.sync",
        target_type="system",
        target_id="parser",
        payload={},
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class MaintenanceModeRequest(BaseModel):
    """Request body for toggling maintenance mode."""
    enabled: bool


@router.post("/system/maintenance", status_code=status.HTTP_204_NO_CONTENT)
async def toggle_maintenance_mode(
    request: MaintenanceModeRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(require_admin_permission(AdminPermission.ROLES_MANAGE)),
) -> Response:
    """
    Toggle system maintenance mode (WRITE, stub implementation).
    
    PHASE 9: Minimal write endpoint with audit logging.
    No real maintenance mode logic - TODO stub only.
    Audit logging is fire-and-forget and won't block the request.
    
    Required permission: ROLES_MANAGE
    
    Args:
        request: Maintenance mode state (enabled: bool)
        user: Current authenticated user (for audit)
    
    Returns:
        204 No Content on success
    """
    # TODO: Implement actual maintenance mode toggle logic
    # For now, this is a stub endpoint that only logs the action
    
    # Audit logging - fire-and-forget, AFTER successful RBAC check
    audit_service = AuditService()
    await audit_service.log_admin_action(
        actor_id=user.id,
        action="admin.system.maintenance",
        target_type="system",
        target_id="core",
        payload={"enabled": request.enabled},
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)
