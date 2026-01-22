"""
RBAC Core - Centralized Permission and Role Definitions (SKELETON ONLY).

This module defines the RBAC model for admin operations:
- Role definitions (SUPERADMIN, ADMIN, MODERATOR)
- Permission definitions
- Role-to-Permission mappings

NOTE: This is a declarative skeleton only. No runtime enforcement logic.
Future phases will add enforcement mechanisms.

SECURITY:
- No wildcard permissions
- Explicit permission enumeration only
"""
from __future__ import annotations

from enum import Enum
from typing import Final


class AdminPermission(str, Enum):
    """
    Admin-specific permissions for parser and system administration.
    
    These map to permissions defined in rbac_contract.ADMIN_PERMISSIONS.
    """
    # Parser administration
    PARSER_SETTINGS = "admin.parser.settings"
    PARSER_EMERGENCY = "admin.parser.emergency"
    PARSER_LOGS = "admin.parser.logs"
    
    # Role and user management
    ROLES_MANAGE = "admin.roles.manage"
    USERS_MANAGE = "admin.users.manage"
    USERS_VIEW = "admin.users.view"


class AdminRole(str, Enum):
    """
    Admin role definitions.
    
    These map to user roles defined in rbac_contract.USER_ROLES.
    """
    SUPERADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"


# Role-to-Permission mappings for admin operations
# This defines what each admin role can do (declarative only)
ADMIN_ROLE_PERMISSIONS: Final[dict[str, frozenset[str]]] = {
    AdminRole.SUPERADMIN: frozenset({
        # Full admin access
        AdminPermission.PARSER_SETTINGS,
        AdminPermission.PARSER_EMERGENCY,
        AdminPermission.PARSER_LOGS,
        AdminPermission.ROLES_MANAGE,
        AdminPermission.USERS_MANAGE,
        AdminPermission.USERS_VIEW,
    }),
    
    AdminRole.ADMIN: frozenset({
        # Admin access without emergency and role management
        AdminPermission.PARSER_SETTINGS,
        AdminPermission.PARSER_LOGS,
        AdminPermission.USERS_VIEW,
    }),
    
    AdminRole.MODERATOR: frozenset({
        # Read-only access
        AdminPermission.PARSER_LOGS,
        AdminPermission.USERS_VIEW,
    }),
}
