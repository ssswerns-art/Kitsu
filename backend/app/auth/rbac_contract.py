"""
RBAC Security Contract - Hard-coded security model with fail-safe enforcement.

This module defines the complete RBAC (Role-Based Access Control) security contract
for the Kitsu backend. This is NOT a convention - it's a hard contract that enforces:
- No privilege escalation
- No implicit permissions
- No mixing of system and user contexts
- No wildcard permissions

ALL changes to this contract must go through security review.
DO NOT modify without explicit approval and separate security task.
"""
from __future__ import annotations

from enum import Enum
from typing import Final, Literal


# ============================================================================
# ACTOR TYPES - IMMUTABLE
# ============================================================================

class ActorType(str, Enum):
    """
    Actor types represent WHO is performing an action.
    These are IMMUTABLE and cannot be extended.
    
    SECURITY INVARIANT: actor_type cannot be spoofed or changed mid-request.
    """
    USER = "user"        # Human user performing actions through UI/API
    SYSTEM = "system"    # Automated system processes (parser, workers)
    ANONYMOUS = "anonymous"  # Unauthenticated requests


# Type alias for strict typing
ActorTypeValue = Literal["user", "system", "anonymous"]

# Frozen set for validation
ALLOWED_ACTOR_TYPES: Final[frozenset[str]] = frozenset({"user", "system", "anonymous"})


# ============================================================================
# ROLES - SEGREGATED BY ACTOR TYPE
# ============================================================================

# User roles - can only be assigned to actor_type="user"
USER_ROLES: Final[frozenset[str]] = frozenset({
    "super_admin",
    "admin",
    "moderator",
    "editor",
    "support",
    "user",
})

# System roles - can only be assigned to actor_type="system"
SYSTEM_ROLES: Final[frozenset[str]] = frozenset({
    "parser_bot",
    "worker_bot",
})

# All valid roles
ALL_ROLES: Final[frozenset[str]] = USER_ROLES | SYSTEM_ROLES


# ============================================================================
# PERMISSIONS - EXPLICIT ONLY, NO WILDCARDS
# ============================================================================

# FORBIDDEN FOREVER - These wildcard patterns are NEVER allowed:
# - "admin:*"
# - "parser:*"
# - "system:*"
# - Any pattern ending with ":*" or ".*"

# Anime permissions
ANIME_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "anime.view",
    "anime.create",
    "anime.edit",
    "anime.delete",
    "anime.publish",
    "anime.lock",
    "anime.unlock",
})

# Episode permissions
EPISODE_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "episode.view",
    "episode.create",
    "episode.edit",
    "episode.delete",
    "episode.lock",
    "episode.unlock",
})

# Parser permissions (system-specific)
PARSER_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "parser.run",
    "parser.configure",
    "parser.override_lock",
})

# Admin permissions (explicit only)
ADMIN_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "admin.parser.settings",
    "admin.parser.emergency",
    "admin.parser.logs",
    "admin.parser.view",
    "admin.parser.manage",
    "admin.roles.manage",
    "admin.roles.view",
    "admin.users.manage",
    "admin.users.view",
})

# Audit permissions
AUDIT_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "audit.view",
})

# Security permissions
SECURITY_PERMISSIONS: Final[frozenset[str]] = frozenset({
    "security.ban.ip",
    "security.unban.ip",
})

# All allowed permissions (explicit enumeration)
ALLOWED_PERMISSIONS: Final[frozenset[str]] = (
    ANIME_PERMISSIONS
    | EPISODE_PERMISSIONS
    | PARSER_PERMISSIONS
    | ADMIN_PERMISSIONS
    | AUDIT_PERMISSIONS
    | SECURITY_PERMISSIONS
)


# ============================================================================
# HARD INVARIANTS - FAIL-FAST ENFORCEMENT
# ============================================================================

def validate_actor_type(actor_type: str) -> None:
    """
    Validate that actor_type is one of the allowed values.
    
    SECURITY: Prevents actor_type spoofing and injection.
    
    Args:
        actor_type: The actor type to validate
        
    Raises:
        ValueError: If actor_type is not allowed
    """
    if actor_type not in ALLOWED_ACTOR_TYPES:
        raise ValueError(
            f"Invalid actor_type '{actor_type}'. "
            f"Must be one of: {', '.join(sorted(ALLOWED_ACTOR_TYPES))}"
        )


def validate_role_for_actor_type(role: str, actor_type: str) -> None:
    """
    Validate that a role is compatible with the actor type.
    
    HARD INVARIANT: System roles cannot be assigned to user actors and vice versa.
    
    Args:
        role: The role to validate
        actor_type: The actor type
        
    Raises:
        ValueError: If role is incompatible with actor_type
    """
    validate_actor_type(actor_type)
    
    if role not in ALL_ROLES:
        raise ValueError(f"Invalid role '{role}'")
    
    if actor_type == ActorType.USER and role in SYSTEM_ROLES:
        raise ValueError(
            f"SECURITY VIOLATION: Cannot assign system role '{role}' to user actor. "
            f"System roles: {', '.join(sorted(SYSTEM_ROLES))}"
        )
    
    if actor_type == ActorType.SYSTEM and role in USER_ROLES:
        raise ValueError(
            f"SECURITY VIOLATION: Cannot assign user role '{role}' to system actor. "
            f"User roles: {', '.join(sorted(USER_ROLES))}"
        )


def validate_permission(permission: str) -> None:
    """
    Validate that a permission is explicitly allowed.
    
    HARD INVARIANT: No wildcard permissions. Every permission must be explicit.
    
    Args:
        permission: The permission to validate
        
    Raises:
        ValueError: If permission contains wildcards or is not allowed
    """
    # Check for forbidden wildcard patterns
    if permission.endswith("*") or permission.endswith(".*") or permission.endswith(":*"):
        raise ValueError(
            f"SECURITY VIOLATION: Wildcard permission '{permission}' is FORBIDDEN. "
            "All permissions must be explicit."
        )
    
    if permission not in ALLOWED_PERMISSIONS:
        raise ValueError(
            f"Invalid permission '{permission}'. "
            f"Permission must be in the allowed list: {sorted(ALLOWED_PERMISSIONS)}"
        )


def check_system_cannot_use_admin_permissions(
    actor_type: str,
    permission: str
) -> None:
    """
    HARD INVARIANT: Parser ≠ Admin
    System actors CANNOT use admin.* permissions.
    
    Args:
        actor_type: The actor type
        permission: The permission being checked
        
    Raises:
        PermissionError: If system actor tries to use admin permission
    """
    if actor_type == ActorType.SYSTEM and permission in ADMIN_PERMISSIONS:
        raise PermissionError(
            f"SECURITY VIOLATION: System actor cannot use admin permission '{permission}'. "
            "Parser ≠ Admin is a hard invariant."
        )


def check_no_implicit_permissions(
    has_role: bool,
    has_explicit_permission: bool
) -> bool:
    """
    HARD INVARIANT: No implicit permissions from roles.
    Access MUST be granted through explicit permission checks only.
    
    Args:
        has_role: Whether the user has the role (IGNORED)
        has_explicit_permission: Whether explicit permission check passed
        
    Returns:
        bool: The explicit permission result (ignores role)
    """
    # Role is ignored - only explicit permission matters
    return has_explicit_permission


# ============================================================================
# ROLE-PERMISSION MAPPINGS (for seeding only)
# ============================================================================

# These mappings are used for database seeding and initialization.
# Runtime permission checks MUST use PermissionService, NOT these mappings.

ROLE_PERMISSION_MAPPINGS: Final[dict[str, frozenset[str]]] = {
    # User roles
    "super_admin": frozenset({
        # All anime permissions
        *ANIME_PERMISSIONS,
        # All episode permissions
        *EPISODE_PERMISSIONS,
        # Parser administration (NOT parser execution)
        "parser.configure",
        "parser.override_lock",
        # All admin permissions
        *ADMIN_PERMISSIONS,
        # All audit permissions
        *AUDIT_PERMISSIONS,
        # All security permissions
        *SECURITY_PERMISSIONS,
    }),
    
    "admin": frozenset({
        # All anime permissions
        *ANIME_PERMISSIONS,
        # All episode permissions
        *EPISODE_PERMISSIONS,
        # Parser administration (NOT parser execution)
        "parser.configure",
        # Subset of admin permissions
        "admin.parser.settings",
        "admin.parser.logs",
        "admin.users.view",
        # Audit access
        "audit.view",
    }),
    
    "moderator": frozenset({
        "anime.view",
        "anime.edit",
        "anime.lock",
        "episode.view",
        "episode.edit",
        "episode.lock",
        "audit.view",
    }),
    
    "editor": frozenset({
        "anime.view",
        "anime.create",
        "anime.edit",
        "episode.view",
        "episode.create",
        "episode.edit",
    }),
    
    "support": frozenset({
        "anime.view",
        "episode.view",
        "admin.users.view",
        "audit.view",
    }),
    
    "user": frozenset({
        "anime.view",
        "episode.view",
    }),
    
    # System roles
    "parser_bot": frozenset({
        "anime.view",
        "anime.create",
        "anime.edit",
        "episode.view",
        "episode.create",
        "episode.edit",
        "parser.run",
        # Parser can override locks for automated updates
        "parser.override_lock",
    }),
    
    "worker_bot": frozenset({
        "anime.view",
        "episode.view",
        # Workers can run background tasks
        "parser.run",
    }),
}


# Validate all mappings at module load time (fail-fast)
def _validate_contract() -> None:
    """Validate the entire RBAC contract at module import time."""
    errors = []
    
    # Validate all permissions in mappings are allowed
    for role, permissions in ROLE_PERMISSION_MAPPINGS.items():
        if role not in ALL_ROLES:
            errors.append(f"Invalid role in mappings: {role}")
            continue
            
        for permission in permissions:
            try:
                validate_permission(permission)
            except ValueError as e:
                errors.append(f"Role '{role}' has invalid permission: {e}")
    
    # Validate no system roles have admin permissions
    for role in SYSTEM_ROLES:
        permissions = ROLE_PERMISSION_MAPPINGS.get(role, frozenset())
        admin_perms = permissions & ADMIN_PERMISSIONS
        if admin_perms:
            errors.append(
                f"SECURITY VIOLATION: System role '{role}' has admin permissions: {admin_perms}"
            )
    
    if errors:
        raise RuntimeError(
            "RBAC Contract validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


# Run validation on import
_validate_contract()
