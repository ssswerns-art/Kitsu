# Admin Core System Documentation

## Overview

The Admin Core system is the foundational administrative layer for the Kitsu application. It provides:

- **Dynamic Role-Based Access Control (RBAC)**: Flexible roles and permissions instead of hardcoded flags
- **Comprehensive Audit Logging**: Every data modification is tracked with before/after states
- **Data Protection**: Lock mechanism to prevent accidental overwrites
- **Soft Delete**: No hard deletes, all deletions are reversible
- **State Machine**: Controlled state transitions for entities
- **System Actors**: Separate permissions for automated systems (parser, cron, etc.)

## Core Principles (Invariants)

These are **HARD RULES** that must never be violated:

1. ❗ **NO actions without permission** - Every action requires explicit permission check
2. ❗ **NO changes without audit** - All modifications must be logged in audit_logs table
3. ❗ **NO delete without soft-delete** - Use `is_deleted` flag instead of DELETE queries
4. ❗ **Parser ≠ Admin** - Parser has different permissions and cannot override manual edits
5. ❗ **Manual > Parser** - Manually created content has priority over parser updates
6. ❗ **UI ≠ Source of Truth** - Frontend permissions are for UX only, backend enforces

## Database Schema

### Core Tables

#### `roles`
- `id` (UUID) - Primary key
- `name` (VARCHAR) - Unique role identifier (e.g., "super_admin", "editor")
- `display_name` (VARCHAR) - Human-readable name
- `description` (TEXT) - Role description
- `is_system` (BOOLEAN) - System-managed role (cannot be deleted)
- `is_active` (BOOLEAN) - Role is active
- `created_at`, `updated_at` (TIMESTAMP)

#### `permissions`
- `id` (UUID) - Primary key
- `name` (VARCHAR) - Unique permission identifier (e.g., "anime.edit")
- `display_name` (VARCHAR) - Human-readable name
- `description` (TEXT) - Permission description
- `resource` (VARCHAR) - Resource type (e.g., "anime", "episode")
- `action` (VARCHAR) - Action type (e.g., "view", "edit", "delete")
- `is_system` (BOOLEAN) - System-managed permission
- `created_at` (TIMESTAMP)

#### `role_permissions`
- `id` (UUID) - Primary key
- `role_id` (UUID FK) - Foreign key to roles
- `permission_id` (UUID FK) - Foreign key to permissions
- `created_at` (TIMESTAMP)

#### `user_roles`
- `id` (UUID) - Primary key
- `user_id` (UUID FK) - Foreign key to users
- `role_id` (UUID FK) - Foreign key to roles
- `granted_by` (UUID FK) - Who granted this role
- `granted_at` (TIMESTAMP)

#### `audit_logs`
- `id` (UUID) - Primary key
- `actor_id` (UUID FK) - Who performed the action
- `actor_type` (VARCHAR) - "user" or "system"
- `action` (VARCHAR) - Action performed (e.g., "anime.edit")
- `entity_type` (VARCHAR) - Entity type affected
- `entity_id` (VARCHAR) - Entity ID affected
- `before` (JSON) - State before change
- `after` (JSON) - State after change
- `reason` (TEXT) - Optional reason for change
- `ip_address` (VARCHAR) - IP address of actor
- `user_agent` (TEXT) - User agent string
- `created_at` (TIMESTAMP) - When action occurred

### Extended Entity Fields

Both `anime` and `episodes` tables now have:

**State Management** (anime only):
- `state` - Current state: draft, pending, published, broken, archived

**Ownership**:
- `created_by` (UUID FK) - Who created this entity
- `updated_by` (UUID FK) - Who last updated this entity
- `source` - Data source: manual, parser, import

**Lock Mechanism**:
- `is_locked` (BOOLEAN) - Is entity locked?
- `locked_fields` (ARRAY) - Specific fields locked (null = all fields)
- `locked_by` (UUID FK) - Who locked it
- `locked_reason` (TEXT) - Why it was locked
- `locked_at` (TIMESTAMP) - When it was locked

**Soft Delete**:
- `is_deleted` (BOOLEAN) - Is entity deleted?
- `deleted_at` (TIMESTAMP) - When deleted
- `deleted_by` (UUID FK) - Who deleted it
- `delete_reason` (TEXT) - Why it was deleted

## Default Roles and Permissions

### Roles

1. **super_admin** - Full system access with all permissions
2. **admin** - Administrative access to manage content and users
3. **moderator** - Can moderate content and handle user reports
4. **editor** - Can create and edit content
5. **parser_bot** - System role for automated parser
6. **support** - Can view audit logs and help users
7. **user** - Regular user with read access

### Permission Categories

- **anime.*** - Anime management permissions
- **episode.*** - Episode management permissions
- **parser.*** - Parser execution and configuration
- **admin.*** - Administrative functions
- **audit.*** - Audit log access
- **security.*** - Security functions

## Services

### PermissionService

Located in `app/services/admin/permission_service.py`

```python
from app.services.admin import PermissionService

# Check if user has permission
has_permission = await permission_service.has_permission(user, "anime.edit")

# Require permission (raises HTTPException if not allowed)
await permission_service.require_permission(user, "anime.edit")

# Get all user permissions
permissions = await permission_service.get_user_permissions(user.id)
```

### AuditService

Located in `app/services/audit/audit_service.py`

```python
from app.services.audit import AuditService

# Log a create event
await audit_service.log_create(
    entity_type="anime",
    entity_id=anime.id,
    entity_data={"title": anime.title, ...},
    actor=current_user,
    reason="Created new anime entry"
)

# Log an update event
await audit_service.log_update(
    entity_type="anime",
    entity_id=anime.id,
    before_data={...},
    after_data={...},
    actor=current_user,
    reason="Updated anime description"
)
```

### LockService

Located in `app/services/admin/lock_service.py`

```python
from app.services.admin import LockService

# Check if update is allowed (raises HTTPException if locked)
LockService.check_lock(
    entity=anime,
    fields_to_update=["description", "poster_url"],
    actor=current_user,
    has_override_permission=False
)

# Check parser update permissions
LockService.check_parser_update(
    entity=anime,
    fields_to_update=["description"],
    actor_type="system"
)
```

## State Machine (Anime)

Valid states and transitions:

```
draft → pending → published
  ↓       ↓          ↓
broken ← → archived
```

**Rules**:
- Parser can only set: `pending`, `broken`
- Parser **CANNOT** set: `published`, `archived`
- Only users with `anime.publish` permission can publish
- State transitions must be validated

## Usage Examples

### Creating an Anime Entry with Audit

```python
from app.services.audit import AuditService
from app.models.anime import Anime

# Create anime
anime = Anime(
    title="New Anime",
    state="draft",
    source="manual",
    created_by=current_user.id,
    updated_by=current_user.id,
)
session.add(anime)
await session.commit()

# Log the creation
audit_service = AuditService(session)
await audit_service.log_create(
    entity_type="anime",
    entity_id=str(anime.id),
    entity_data=LockService.serialize_entity(anime),
    actor=current_user,
    reason="Created new anime entry"
)
```

### Locking an Anime Entry

```python
from app.services.admin import PermissionService

# Check permission
permission_service = PermissionService(session)
await permission_service.require_permission(current_user, "anime.lock")

# Lock specific fields
anime.is_locked = True
anime.locked_fields = ["title", "description"]  
anime.locked_by = current_user.id
anime.locked_reason = "Official title, do not modify"
anime.locked_at = datetime.now(timezone.utc)

await session.commit()

# Log the lock
await audit_service.log_lock(
    entity_type="anime",
    entity_id=str(anime.id),
    locked_fields=["title", "description"],
    actor=current_user,
    reason="Official title, do not modify"
)
```

### Parser Update with Lock Check

```python
from app.services.admin import LockService

# Parser trying to update anime
LockService.check_parser_update(
    entity=anime,
    fields_to_update=["description", "poster_url"],
    actor_type="system"
)

# If no exception raised, update is allowed
anime.description = new_description
anime.updated_by = None  # System update
anime.source = "parser"

# Log the update
await audit_service.log_update(
    entity_type="anime",
    entity_id=str(anime.id),
    before_data={"description": old_description},
    after_data={"description": new_description},
    actor=None,
    actor_type="system"
)
```

## Setup Instructions

### 1. Run Migration

```bash
cd backend
alembic upgrade head
```

### 2. Seed Default Roles and Permissions

```bash
cd backend
python -m scripts.seed_admin_core
```

This will create:
- 7 default roles
- 21 default permissions
- Role-permission assignments

### 3. Assign Roles to Users

```python
from app.crud.role import RoleRepository

role_repo = RoleRepository(session)
role = await role_repo.get_by_name("admin")
await role_repo.assign_to_user(
    user_id=user.id,
    role_id=role.id,
    granted_by=granter_user.id
)
```

## Best Practices

### DO:
✅ Always check permissions before actions
✅ Log all data modifications to audit_logs
✅ Use soft delete for all deletions
✅ Check locks before updating entities
✅ Separate parser and admin permissions
✅ Provide reasons for locks and deletes

### DON'T:
❌ Hard-code role checks (use permission system)
❌ Skip audit logging
❌ Use SQL DELETE (use soft delete)
❌ Allow parser to override locks
❌ Trust frontend permissions
❌ Allow parser to publish content

## Future Enhancements

- Admin UI for role/permission management
- Audit log viewer with filtering
- Automated lock expiration
- Permission templates
- Role inheritance
- Audit log retention policies

## Troubleshooting

### Migration Issues
If migration fails, check:
1. Database connection string
2. Previous migrations are applied
3. No duplicate constraint names

### Seed Script Issues
If seeding fails:
1. Ensure migration is applied first
2. Check database connection
3. Script is idempotent, can be re-run safely

### Permission Denied
If getting permission errors:
1. Verify user has role assigned
2. Check role has required permission
3. Ensure role is active
4. Review audit logs for details
