# RBAC Security Model (SECURITY-01)

## Overview

This document describes the hardened Role-Based Access Control (RBAC) security model implemented in the Kitsu backend. This is a **hard contract**, not a convention. All security invariants are enforced at runtime with fail-fast behavior.

## Security Goals

The RBAC system is designed to prevent:
- ❌ Privilege escalation
- ❌ Implicit permissions
- ❌ Mixing of system and user contexts
- ❌ Wildcard permissions

## Core Concepts

### Actor Types (Immutable)

Every action in the system is performed by an **actor** with a specific type:

| Actor Type | Description | Examples |
|------------|-------------|----------|
| `user` | Human users accessing the system | Regular users, admins, moderators |
| `system` | Automated system processes | Parser bot, worker bot |
| `anonymous` | Unauthenticated requests | Public API access |

**Security Invariant**: Actor types are validated at every layer (ORM, service, audit).

### Roles

Roles are assigned to actors and determine their capabilities. Roles are **segregated by actor type**:

#### User Roles (actor_type="user")
- `super_admin` - Full system access
- `admin` - Administrative access
- `moderator` - Content moderation
- `editor` - Content creation/editing
- `support` - User support and audit access
- `user` - Regular user

#### System Roles (actor_type="system")
- `parser_bot` - Automated content parsing
- `worker_bot` - Background task processing

**Security Invariant**: System roles CANNOT be assigned to user actors and vice versa.

### Permissions

Permissions are **explicit actions** that can be performed. Every permission must be:
1. Explicitly defined in `rbac_contract.py`
2. Free of wildcards (no `*`, `.*`, `:*`)
3. Granted through database, never assumed from roles

#### Permission Categories

**Anime Permissions**
- `anime.view`, `anime.create`, `anime.edit`, `anime.delete`
- `anime.publish`, `anime.lock`, `anime.unlock`

**Episode Permissions**
- `episode.view`, `episode.create`, `episode.edit`, `episode.delete`
- `episode.lock`, `episode.unlock`

**Parser Permissions** (system-specific)
- `parser.run` - Execute parser jobs
- `parser.configure` - Configure parser settings
- `parser.override_lock` - Override content locks

**Admin Permissions** (explicit only)
- `admin.parser.settings` - Manage parser settings
- `admin.parser.emergency` - Emergency parser controls
- `admin.parser.logs` - View parser logs
- `admin.roles.manage` - Manage roles and permissions
- `admin.users.manage` - Manage user accounts
- `admin.users.view` - View user information

**Audit Permissions**
- `audit.view` - View audit logs

**Security Permissions**
- `security.ban.ip` - Ban IP addresses
- `security.unban.ip` - Unban IP addresses

## Hard Invariants (Fail-Fast)

These invariants are **enforced at runtime**. Violations result in immediate exceptions.

### 1. Parser ≠ Admin

```python
# FORBIDDEN: System actors CANNOT use admin permissions
actor_type = "system"
permission = "admin.parser.settings"
# ❌ Raises PermissionError
```

**Rationale**: Prevents automated systems from gaining administrative privileges.

### 2. System ≠ User

```python
# FORBIDDEN: Cannot assign user roles to system actors
actor_type = "system"
role = "admin"
# ❌ Raises ValueError
```

**Rationale**: Prevents privilege confusion and escalation.

### 3. No Implicit Permissions

```python
# FORBIDDEN: Having a role does not grant permission
user.role = "admin"
# ❌ This does NOT grant any permissions

# REQUIRED: Permission must be explicitly granted
permission_service.has_permission(user, "anime.edit")
# ✅ Checks database for explicit grant
```

**Rationale**: Roles are organizational labels. Permissions are explicit grants.

### 4. No Wildcards

```python
# FORBIDDEN FOREVER:
"admin:*"     # ❌ No wildcard permissions
"parser:*"    # ❌ No wildcard permissions
"system:*"    # ❌ No wildcard permissions
"admin.*"     # ❌ No pattern matching

# REQUIRED: Use explicit permissions
"admin.parser.settings"   # ✅ Explicit
"admin.parser.emergency"  # ✅ Explicit
"admin.parser.logs"       # ✅ Explicit
```

**Rationale**: Wildcards enable privilege escalation. All permissions must be explicit.

## Enforcement Architecture

### Layer 1: Contract Validation (`rbac_contract.py`)

```python
from app.auth import rbac_contract

# Validates actor type
rbac_contract.validate_actor_type("user")  # ✅

# Validates permission (no wildcards)
rbac_contract.validate_permission("anime.edit")  # ✅
rbac_contract.validate_permission("admin:*")  # ❌ Raises ValueError

# Validates role assignment
rbac_contract.validate_role_for_actor_type("admin", "user")  # ✅
rbac_contract.validate_role_for_actor_type("parser_bot", "user")  # ❌ Raises ValueError
```

### Layer 2: Service Enforcement (`PermissionService`)

**All permission checks MUST go through PermissionService**:

```python
from app.services.admin.permission_service import PermissionService

# Check permission with hard invariant enforcement
has_perm = await permission_service.has_permission(
    user=current_user,
    permission_name="anime.edit",
    actor_type="user"
)

# Require permission (raises 403 if denied)
await permission_service.require_permission(
    user=current_user,
    permission_name="admin.users.view",
    actor_type="user"
)
```

**Inline role checks are FORBIDDEN**:
```python
# ❌ FORBIDDEN - Inline role check
if user.role == "admin":
    allow_access()

# ✅ REQUIRED - PermissionService check
if await permission_service.has_permission(user, "anime.edit"):
    allow_access()
```

### Layer 3: Database Validation (`AuditLog` model)

Actor type is validated at multiple levels:

1. **ORM validator** (`@validates`)
2. **Database constraint** (`CHECK` constraint)

```python
# Audit logging with actor_type validation
await audit_service.log(
    action="anime.edit",
    entity_type="anime",
    entity_id="123",
    actor=user,
    actor_type="user"  # Validated at ORM and DB level
)
```

## Audit Requirements

All security events MUST be logged:

### Required Audit Logs

1. **Permission Denied (403)**
```python
await audit_service.log_permission_denied(
    permission="anime.edit",
    actor=user,
    actor_type="user",
    resource="anime/123"
)
```

2. **Privilege Escalation Attempts**
```python
await audit_service.log_privilege_escalation_attempt(
    actor=user,
    actor_type="user",
    attempted_role="admin",
    attempted_permission="admin.users.manage"
)
```

3. **Role Changes** (via standard audit log)
4. **Permission Changes** (via standard audit log)

## Security Checklist

When adding new features:

- [ ] All permission checks use `PermissionService`
- [ ] No inline role checks (`if role == "admin"`)
- [ ] No wildcard permissions
- [ ] Actor type validated for all audit logs
- [ ] Permission denied events logged (automatically via PermissionService.require_permission)
- [ ] Privilege escalation attempts logged (if applicable)
- [ ] New permissions added to `rbac_contract.py`
- [ ] Tests verify hard invariants

## Migration Guide

### Replacing Legacy Code

**Before (INSECURE)**:
```python
# Wildcard permission
if "admin:*" in user_permissions:
    allow_access()

# Inline role check
if user.role == "admin":
    allow_access()
```

**After (SECURE)**:
```python
# Explicit permission through service
if await permission_service.has_permission(user, "admin.parser.settings"):
    allow_access()
```

## Contract Modification Policy

**CRITICAL**: Changes to `rbac_contract.py` require:

1. ✅ Separate security review task
2. ✅ Security team approval
3. ✅ All tests passing
4. ✅ CodeQL scan passing
5. ✅ Updated audit logs

**DO NOT**:
- ❌ Add temporary bypasses
- ❌ Add wildcard permissions "to remove later"
- ❌ Grant system actors admin permissions
- ❌ Modify hard invariants without approval

## Testing

Run all RBAC security tests:

```bash
# Contract validation tests
pytest tests/test_rbac_contract.py -v

# PermissionService security tests
pytest tests/test_permission_service_security.py -v

# AuditService security tests
pytest tests/test_audit_service_security.py -v
```

All tests must pass before merging.

## References

- **Contract Definition**: `backend/app/auth/rbac_contract.py`
- **Permission Service**: `backend/app/services/admin/permission_service.py`
- **Audit Service**: `backend/app/services/audit/audit_service.py`
- **Seed Script**: `backend/scripts/seed_admin_core.py`
- **Tests**: `backend/tests/test_rbac_contract.py`

## Security Contact

For security concerns or questions about this contract:
- Create a security task with tag `SECURITY`
- Do not make changes without explicit approval
