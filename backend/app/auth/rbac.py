"""
DEPRECATED: This module is being phased out in favor of rbac_contract.py

For legacy compatibility only. New code should use:
- app.auth.rbac_contract for the security contract
- app.services.admin.permission_service.PermissionService for runtime checks

SECURITY WARNING: This module contains legacy code with deprecated patterns.
DO NOT extend or modify. Use PermissionService for all permission checks.
"""
from __future__ import annotations

from typing import Final

from ..models.user import User

Role = str
Permission = str

# LEGACY: These are kept for backward compatibility only
# New code should use rbac_contract.ALLOWED_PERMISSIONS
BASE_ROLES: Final[tuple[Role, ...]] = ("guest", "user", "admin")

# SECURITY: Wildcard permissions removed per SECURITY-01
# Old: "admin:*" - FORBIDDEN
# Use explicit permissions: admin.parser.settings, admin.parser.emergency, admin.parser.logs
BASE_PERMISSIONS: Final[tuple[Permission, ...]] = (
    "read:profile",
    "write:profile",
    "read:content",
    "write:content",
    # Explicit admin permissions (no wildcards)
    "admin.parser.settings",
    "admin.parser.emergency",
    "admin.parser.logs",
)

# LEGACY: Simple role-permission mapping
# Runtime permission checks MUST use PermissionService, not this mapping
ROLE_PERMISSIONS: Final[dict[Role, tuple[Permission, ...]]] = {
    "guest": ("read:content",),
    "user": ("read:profile", "write:profile", "read:content", "write:content"),
    "admin": (
        "read:profile",
        "write:profile",
        "read:content",
        "write:content",
        # Explicit admin permissions only (wildcard "admin:*" removed)
        "admin.parser.settings",
        "admin.parser.emergency",
        "admin.parser.logs",
    ),
}


def resolve_role(user: User | None) -> Role:
    """
    LEGACY: Resolve a simple role from a user object.
    
    DEPRECATED: This function does not enforce the full RBAC contract.
    New code should use proper role assignment from database with actor_type validation.
    """
    if user is None:
        return "guest"
    user_role = getattr(user, "role", None)
    if user_role in BASE_ROLES:
        return user_role
    if getattr(user, "is_admin", False) or getattr(user, "is_superuser", False):
        return "admin"
    return "user"


def resolve_permissions(role: Role) -> list[Permission]:
    """
    LEGACY: Get permissions for a role from hardcoded mapping.
    
    DEPRECATED: This does not enforce hard invariants or check against contract.
    Runtime permission checks MUST use PermissionService.has_permission() instead.
    """
    return list(ROLE_PERMISSIONS.get(role, ()))

