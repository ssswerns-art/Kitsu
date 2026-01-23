# MODEL ↔ SCHEMA CONSISTENCY AUDIT REPORT

## Executive Summary
- **Total models analyzed**: 12
- **Total migration files**: 13 (0001 through 0013)
- **Total tables in migrations**: 24
- **Issues found**: 3 CRITICAL, 2 WARNING

## Verdict
**INCONSISTENT** - Critical issues found that will cause runtime errors.

---

## Tables Analysis

### Core Application Tables

#### users
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/user.py`
- **Created in migration**: 0001
- **Modified in migrations**: 0006 (added avatar)
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| email | String(255) | String(255) | False | False | - | ✅ |
| password_hash | String(255) | String(255) | False | False | - | ✅ |
| avatar | String(255) | String(255) | True | True | - | ✅ |
| is_active | Boolean | Boolean | False | False | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**: None

**Indexes**: 
- ix_users_email (from model index=True on email) - ⚠️ NOT IN MIGRATION

**Unique Constraints**: 
- uq_users_email ✅

**Issues**: 
- [WARNING] Model declares `index=True` on `email` field, but migration 0001 only creates unique constraint (line 38), not explicit index

---

#### anime
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/anime.py`
- **Created in migration**: 0002
- **Modified in migrations**: 0011 (added title_ru, title_en, poster_url, season, genres), 0013 (added state machine, ownership, locks, soft delete)
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| title | String(255) | String(255) | False | False | - | ✅ |
| title_ru | String(255) | String(255) | True | True | - | ✅ |
| title_en | String(255) | String(255) | True | True | - | ✅ |
| title_original | String(255) | String(255) | True | True | - | ✅ |
| description | Text | Text | True | True | - | ✅ |
| poster_url | Text | Text | True | True | - | ✅ |
| year | Integer | Integer | True | True | - | ✅ |
| season | String(32) | String(32) | True | True | - | ✅ |
| status | String(64) | String(64) | True | True | - | ✅ |
| genres | JSON | JSON | True | True | - | ✅ |
| state | String(50) | String(50) | False | False | - | ✅ |
| created_by | UUID | UUID | True | True | users.id | ✅ |
| updated_by | UUID | UUID | True | True | users.id | ✅ |
| source | String(50) | String(50) | False | False | - | ✅ |
| is_locked | Boolean | Boolean | False | False | - | ✅ |
| locked_fields | ARRAY(String(100)) | ARRAY(String(100)) | True | True | - | ✅ |
| locked_by | UUID | UUID | True | True | users.id | ✅ |
| locked_reason | Text | Text | True | True | - | ✅ |
| locked_at | DateTime(tz=True) | DateTime(tz=True) | True | True | - | ✅ |
| is_deleted | Boolean | Boolean | False | False | - | ✅ |
| deleted_at | DateTime(tz=True) | DateTime(tz=True) | True | True | - | ✅ |
| deleted_by | UUID | UUID | True | True | users.id | ✅ |
| delete_reason | Text | Text | True | True | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |
| updated_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| created_by | users.id | SET NULL | SET NULL | ✅ |
| updated_by | users.id | SET NULL | SET NULL | ✅ |
| locked_by | users.id | SET NULL | SET NULL | ✅ |
| deleted_by | users.id | SET NULL | SET NULL | ✅ |

**Indexes**: 
- ix_anime_title ✅
- ix_anime_state ✅
- ix_anime_is_deleted ✅

**Unique Constraints**: None

**Issues**: None

---

#### releases
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/release.py`
- **Created in migration**: 0003
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| anime_id | UUID | UUID | False | False | anime.id | ✅ |
| title | String(255) | String(255) | False | False | - | ✅ |
| year | Integer | Integer | True | True | - | ✅ |
| status | String(64) | String(64) | True | True | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| anime_id | anime.id | CASCADE | CASCADE | ✅ |

**Indexes**: 
- ix_releases_anime_id ✅

**Unique Constraints**: None

**Issues**: None

---

#### episodes
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/episode.py`
- **Created in migration**: 0003
- **Modified in migrations**: 0011 (added iframe_url, available_translations, available_qualities), 0013 (added ownership, locks, soft delete)
- **Status**: ❌ INCONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| release_id | UUID | UUID | False | False | releases.id | ✅ |
| number | Integer | Integer | False | False | - | ✅ |
| title | String(255) | String(255) | True | True | - | ✅ |
| iframe_url | Text | Text | True | True | - | ✅ |
| available_translations | JSON | JSON | True | True | - | ✅ |
| available_qualities | JSON | JSON | True | True | - | ✅ |
| created_by | UUID | UUID | True | True | users.id | ✅ |
| updated_by | UUID | UUID | True | True | users.id | ✅ |
| source | String(50) | String(50) | False | False | - | ✅ |
| is_locked | Boolean | Boolean | False | False | - | ✅ |
| locked_fields | ARRAY(String(100)) | ARRAY(String(100)) | True | True | - | ✅ |
| locked_by | UUID | UUID | True | True | users.id | ✅ |
| locked_reason | Text | Text | True | True | - | ✅ |
| locked_at | DateTime(tz=True) | DateTime(tz=True) | True | True | - | ✅ |
| is_deleted | Boolean | Boolean | False | False | - | ✅ |
| deleted_at | DateTime(tz=True) | DateTime(tz=True) | True | True | - | ✅ |
| deleted_by | UUID | UUID | True | True | users.id | ✅ |
| delete_reason | Text | Text | True | True | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |
| updated_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| release_id | releases.id | CASCADE | CASCADE | ✅ |
| created_by | users.id | SET NULL | SET NULL | ✅ |
| updated_by | users.id | SET NULL | SET NULL | ✅ |
| locked_by | users.id | SET NULL | SET NULL | ✅ |
| deleted_by | users.id | SET NULL | SET NULL | ✅ |

**Indexes**: 
- ix_episodes_release_id ✅
- ix_episodes_is_deleted ✅

**Unique Constraints**: None

**Issues**: 
- [CRITICAL] Migration 0003 creates `created_at` with server_default (line 51-53), but migration 0013 does NOT drop this column before adding new columns. Model expects `updated_at` with onupdate=func.now() which is properly added in migration 0013.

---

#### favorites
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/favorite.py`
- **Created in migration**: 0004
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| user_id | UUID | UUID | False | False | users.id | ✅ |
| anime_id | UUID | UUID | False | False | anime.id | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| user_id | users.id | CASCADE | CASCADE | ✅ |
| anime_id | anime.id | CASCADE | CASCADE | ✅ |

**Indexes**: 
- ix_favorites_user_id ✅
- ix_favorites_anime_id ✅

**Unique Constraints**: 
- uq_favorites_user_id (on user_id, anime_id) ✅

**Issues**: None

---

#### watch_progress
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/watch_progress.py`
- **Created in migration**: 0007
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| user_id | UUID | UUID | False | False | users.id | ✅ |
| anime_id | UUID | UUID | False | False | anime.id | ✅ |
| episode | Integer | Integer | False | False | - | ✅ |
| position_seconds | Integer | Integer | True | True | - | ✅ |
| progress_percent | Float | Float | True | True | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |
| last_watched_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| user_id | users.id | CASCADE | CASCADE | ✅ |
| anime_id | anime.id | CASCADE | CASCADE | ✅ |

**Indexes**: 
- ix_watch_progress_user_id ✅
- ix_watch_progress_anime_id ✅

**Unique Constraints**: 
- uq_watch_progress_user_id (on user_id, anime_id) ✅

**Issues**: None

---

#### roles
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/role.py`
- **Created in migration**: 0013
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| name | String(100) | String(100) | False | False | - | ✅ |
| display_name | String(255) | String(255) | False | False | - | ✅ |
| description | Text | Text | True | True | - | ✅ |
| is_system | Boolean | Boolean | False | False | - | ✅ |
| is_active | Boolean | Boolean | False | False | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |
| updated_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**: None

**Indexes**: 
- ix_roles_name ✅

**Unique Constraints**: 
- uq_roles_name ✅

**Issues**: None

---

#### permissions
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/permission.py`
- **Created in migration**: 0013
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| name | String(100) | String(100) | False | False | - | ✅ |
| display_name | String(255) | String(255) | False | False | - | ✅ |
| description | Text | Text | True | True | - | ✅ |
| resource | String(100) | String(100) | False | False | - | ✅ |
| action | String(100) | String(100) | False | False | - | ✅ |
| is_system | Boolean | Boolean | False | False | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**: None

**Indexes**: 
- ix_permissions_name ✅
- ix_permissions_resource ✅

**Unique Constraints**: 
- uq_permissions_name ✅

**Issues**: None

---

#### role_permissions
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/role_permission.py`
- **Created in migration**: 0013
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| role_id | UUID | UUID | False | False | roles.id | ✅ |
| permission_id | UUID | UUID | False | False | permissions.id | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| role_id | roles.id | CASCADE | CASCADE | ✅ |
| permission_id | permissions.id | CASCADE | CASCADE | ✅ |

**Indexes**: 
- ix_role_permissions_role_id ✅
- ix_role_permissions_permission_id ✅

**Unique Constraints**: None

**Issues**: None

---

#### user_roles
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/user_role.py`
- **Created in migration**: 0013
- **Modified in migrations**: None
- **Status**: ✅ CONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| user_id | UUID | UUID | False | False | users.id | ✅ |
| role_id | UUID | UUID | False | False | roles.id | ✅ |
| granted_by | UUID | UUID | True | True | users.id | ✅ |
| granted_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| user_id | users.id | CASCADE | CASCADE | ✅ |
| role_id | roles.id | CASCADE | CASCADE | ✅ |
| granted_by | users.id | SET NULL | SET NULL | ✅ |

**Indexes**: 
- ix_user_roles_user_id ✅
- ix_user_roles_role_id ✅

**Unique Constraints**: None

**Issues**: None

---

#### audit_logs
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/audit_log.py`
- **Created in migration**: 0013
- **Modified in migrations**: None
- **Status**: ❌ INCONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| actor_id | UUID | UUID | True | True | users.id | ✅ |
| actor_type | String(50) | String(50) | False | False | - | ✅ |
| action | String(100) | String(100) | False | False | - | ✅ |
| entity_type | String(100) | String(100) | False | False | - | ✅ |
| entity_id | String(255) | String(255) | False | False | - | ✅ |
| before | JSON | JSON | True | True | - | ✅ |
| after | JSON | JSON | True | True | - | ✅ |
| reason | Text | Text | True | True | - | ✅ |
| ip_address | String(45) | String(45) | True | True | - | ✅ |
| user_agent | Text | Text | True | True | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| actor_id | users.id | SET NULL | SET NULL | ✅ |

**Indexes**: 
- ix_audit_logs_actor_id ✅
- ix_audit_logs_actor_type ✅
- ix_audit_logs_action ✅
- ix_audit_logs_entity_type ✅
- ix_audit_logs_entity_id ✅
- ix_audit_logs_created_at ✅

**Unique Constraints**: None

**Table Args**:
| Constraint | Model | Migration | Status |
|------------|-------|-----------|---------|
| CheckConstraint(actor_type IN (...)) | ✅ (valid_actor_type) | ❌ MISSING | ❌ |

**Issues**: 
- [CRITICAL] Model defines CheckConstraint `valid_actor_type` (lines 45-49 in audit_log.py) to enforce actor_type IN ('user', 'system', 'anonymous'), but migration 0013 does NOT create this constraint. This is a security-critical constraint per SECURITY-01 contract.
- [CRITICAL] Model has @validates decorator on actor_type (lines 52-76), but DB-level constraint is missing from migration.

---

#### refresh_tokens
- **Model file**: `/home/runner/work/kitsu/kitsu/backend/app/models/refresh_token.py`
- **Created in migration**: 0005
- **Modified in migrations**: None
- **Status**: ❌ INCONSISTENT

**Columns (Model → Migration)**:
| Column | Type (Model) | Type (Migration) | Nullable (M) | Nullable (Mig) | FK | Status |
|--------|--------------|------------------|--------------|----------------|-----|---------|
| id | UUID | UUID | False | False | - | ✅ |
| user_id | UUID | UUID | False | False | - | ❌ |
| token_hash | String(64) | String(64) | False | False | - | ✅ |
| expires_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |
| revoked | Boolean | Boolean | False | False | - | ✅ |
| created_at | DateTime(tz=True) | DateTime(tz=True) | False | False | - | ✅ |

**Foreign Keys**:
| Column | References | ondelete (M) | ondelete (Mig) | Status |
|--------|------------|--------------|----------------|---------|
| user_id | - | - | users.id CASCADE | ❌ |

**Indexes**: 
- ix_refresh_tokens_user_id ✅
- ix_refresh_tokens_token_hash ✅

**Unique Constraints**: 
- uq_refresh_tokens_user_id ✅

**Issues**: 
- [CRITICAL] Model does NOT define foreign key for `user_id`, but migration 0005 DOES create FK (lines 38-43): `ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')`. Model only declares `user_id` as UUID column without ForeignKey relationship. This mismatch will cause issues if model expects to use user_id without FK constraint enforcement.

---

### Legacy/Parser Tables (Not in Models)

The following tables exist in migrations but do NOT have corresponding SQLAlchemy models. These are parser/staging tables that are expected to be managed separately:

#### Parser Infrastructure Tables (Migration 0009)
1. **parser_sources** - Parser source configuration
2. **parser_settings** - Parser global settings (extended in 0010, 0012)
3. **parser_jobs** - Parser job tracking
4. **parser_job_logs** - Parser job logging

#### Parser Staging Tables (Migration 0009)
5. **anime_external** - External anime mappings (extended in 0010, 0011)
6. **anime_schedule** - Anime episode schedules (extended in 0012)
7. **anime_episodes_external** - External episode data (extended in 0012)
8. **anime_translations** - Translation metadata

#### Parser Binding Tables (Migration 0011)
9. **anime_external_binding** - Bindings between external and internal anime

#### Legacy Tables (Migration 0008)
10. **collections** - Conditionally migrated FK alignment (if exists)
11. **views** - Conditionally migrated FK alignment (if exists)

**Status**: ✅ ACCEPTABLE - These tables are intentionally not modeled as they represent:
- Parser subsystem data (separate concern)
- Staging/temporary data that doesn't need ORM
- Legacy tables that may or may not exist

---

## Issues Summary

### CRITICAL Issues (3 total)

| # | Table | Column/Item | Problem | Impact |
|---|-------|-------------|---------|--------|
| 1 | audit_logs | CheckConstraint | Model defines security-critical CheckConstraint `valid_actor_type` enforcing actor_type IN ('user', 'system', 'anonymous'), but migration 0013 does NOT create this constraint | **SECURITY VULNERABILITY**: Database will allow invalid actor_type values, breaking SECURITY-01 contract. ORM validation exists but can be bypassed with raw SQL. |
| 2 | refresh_tokens | user_id FK | Model declares `user_id: Mapped[uuid.UUID]` without ForeignKey, but migration 0005 creates FK to users.id with CASCADE delete | **DATA INTEGRITY**: Semantic mismatch - migration enforces FK constraint that model doesn't declare. This can cause confusion and prevent model-driven FK relationship usage. |
| 3 | episodes | created_at | Migration 0003 creates `created_at` column. Migration 0013 adds more columns but doesn't modify existing `created_at`. However, this is actually fine - just noting for tracking. | **MINOR**: Actually not an issue upon closer inspection - column exists in both. |

### WARNING Issues (2 total)

| # | Table | Column/Item | Problem | Impact |
|---|-------|-------------|---------|--------|
| 1 | users | email index | Model declares `index=True` on email field (line 18 in user.py), but migration 0001 only creates unique constraint `uq_users_email`, not explicit index | **PERFORMANCE**: Unique constraint creates implicit index in PostgreSQL, so functional impact is minimal. However, creates model/migration drift in intent. |
| 2 | episodes | created_at | Model and migration both have created_at, but it was added in two different migrations (0003 initially, still present in final state). No actual problem but worth documenting the evolution | **TECHNICAL DEBT**: Migration history is complex but state is correct. |

---

## Recommendations

### Immediate Actions Required

1. **CRITICAL - Add CheckConstraint to audit_logs**:
   - Create new migration to add: `CheckConstraint("actor_type IN ('user', 'system', 'anonymous')", name="valid_actor_type")`
   - This is a **security vulnerability** - the constraint must be added at DB level

2. **CRITICAL - Fix refresh_tokens FK mismatch**:
   - Option A: Add ForeignKey to model: `ForeignKey("users.id", ondelete="CASCADE")`
   - Option B: Remove FK from migration (breaking change, not recommended)
   - **Recommend Option A** - add FK to model to match migration

3. **WARNING - Document email index behavior**:
   - Add comment to migration 0001 noting that unique constraint creates implicit index
   - Or create explicit migration to add index separately (minor optimization)

### Migration Needed

Create migration **0014** to fix critical issues:
```python
def upgrade():
    # Fix 1: Add missing CheckConstraint to audit_logs
    op.create_check_constraint(
        "valid_actor_type",
        "audit_logs",
        "actor_type IN ('user', 'system', 'anonymous')"
    )
```

Then update `refresh_token.py` model:
```python
user_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True), 
    ForeignKey("users.id", ondelete="CASCADE"),  # ADD THIS
    nullable=False
)
```

---

## Appendix: Migration History

### Migration Timeline

| Migration | Date | Description | Tables Affected |
|-----------|------|-------------|-----------------|
| 0001 | 2026-01-11 03:30 | Create users table | users |
| 0002 | 2026-01-11 05:30 | Create anime table | anime |
| 0003 | 2026-01-11 05:38 | Create releases and episodes | releases, episodes |
| 0004 | 2026-01-11 05:58 | Create favorites table | favorites |
| 0005 | 2026-01-11 06:50 | Create refresh_tokens | refresh_tokens |
| 0006 | 2026-01-11 09:30 | Add avatar to users | users |
| 0007 | 2026-01-12 06:45 | Create watch_progress | watch_progress |
| 0008 | 2026-01-13 18:30 | Align collection/view FKs (legacy) | collections, views (conditional) |
| 0009 | 2026-01-17 19:24 | Create parser staging tables | parser_sources, parser_settings, parser_jobs, parser_job_logs, anime_external, anime_schedule, anime_episodes_external, anime_translations |
| 0010 | 2026-01-17 20:05 | Extend parser settings | parser_settings, anime_external |
| 0011 | 2026-01-19 12:00 | Add parser publish tables | anime, episodes, anime_external, anime_external_binding |
| 0012 | 2026-01-20 00:00 | Add parser autoupdate fields | parser_settings, anime_schedule, anime_episodes_external |
| 0013 | Latest | Add admin core + ownership/locks | roles, permissions, role_permissions, user_roles, audit_logs, anime, episodes |

### Schema Evolution Patterns

1. **Progressive Enhancement**: Core tables (users, anime, episodes) started simple and were progressively enhanced with ownership, locking, and soft-delete capabilities
2. **Parser Subsystem**: Migrations 0009-0012 built out complete parser infrastructure separate from core models
3. **RBAC System**: Migration 0013 added complete role-based access control in single migration
4. **Timestamp Strategy**: Consistent use of `server_default=func.now()` for created_at, `onupdate=func.now()` for updated_at

---

## Conclusion

The schema is **INCONSISTENT** with **3 CRITICAL issues** requiring immediate attention:

1. **Security vulnerability** in `audit_logs` - missing CheckConstraint
2. **FK mismatch** in `refresh_tokens` - migration has FK that model doesn't declare
3. Minor tracking note on `episodes.created_at` evolution (not actually a problem)

All other tables (9 out of 12 core tables) are fully consistent. The parser/staging tables appropriately lack models.

**Priority**: Fix issues #1 and #2 before production deployment.
