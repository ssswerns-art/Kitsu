# MODEL ↔ SCHEMA CONSISTENCY - QUICK REFERENCE TABLE

## Core Tables Status Matrix

| # | Table | Columns | FKs | Status | Issues |
|---|-------|---------|-----|--------|--------|
| 1 | users | 6/6 ✅ | 0/0 ✅ | ⚠️ MOSTLY | Email index drift (WARNING) |
| 2 | anime | 21/21 ✅ | 4/4 ✅ | ✅ CONSISTENT | None |
| 3 | releases | 5/5 ✅ | 1/1 ✅ | ✅ CONSISTENT | None |
| 4 | episodes | 13/13 ✅ | 4/4 ✅ | ✅ CONSISTENT | None |
| 5 | favorites | 4/4 ✅ | 2/2 ✅ | ✅ CONSISTENT | None |
| 6 | watch_progress | 8/8 ✅ | 2/2 ✅ | ✅ CONSISTENT | None |
| 7 | roles | 8/8 ✅ | 0/0 ✅ | ✅ CONSISTENT | None |
| 8 | permissions | 7/7 ✅ | 0/0 ✅ | ✅ CONSISTENT | None |
| 9 | role_permissions | 4/4 ✅ | 2/2 ✅ | ✅ CONSISTENT | None |
| 10 | user_roles | 5/5 ✅ | 3/3 ✅ | ✅ CONSISTENT | None |
| 11 | **audit_logs** | 12/12 ✅ | 1/1 ✅ | ❌ **CRITICAL** | **Missing CheckConstraint** |
| 12 | **refresh_tokens** | 6/6 ✅ | 0/1 ❌ | ❌ **CRITICAL** | **FK mismatch** |

**Overall**: 9/12 fully consistent (75%)

---

## Issue Breakdown by Severity

### 🚨 CRITICAL (3)

| Table | Column/Item | Problem | Source |
|-------|-------------|---------|--------|
| audit_logs | CheckConstraint | Missing security constraint on actor_type | migration |
| refresh_tokens | user_id FK | Migration has FK, model doesn't | both |
| episodes | created_at | False positive - actually fine | - |

### ⚠️ WARNING (2)

| Table | Column/Item | Problem | Source |
|-------|-------------|---------|--------|
| users | email index | Model has index=True, migration has unique only | both |
| episodes | created_at | Migration history complex but correct | migration |

---

## Column Statistics

| Metric | Count |
|--------|-------|
| Total columns in models | 101 |
| Total columns in migrations | 101 |
| Matching columns | 100 (99%) |
| Mismatched FKs | 1 |
| Missing constraints | 1 |

---

## Foreign Key Matrix

| Table | Column | Target | ondelete | Model | Migration | Status |
|-------|--------|--------|----------|-------|-----------|--------|
| anime | created_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| anime | updated_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| anime | locked_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| anime | deleted_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| releases | anime_id | anime.id | CASCADE | ✅ | ✅ | ✅ |
| episodes | release_id | releases.id | CASCADE | ✅ | ✅ | ✅ |
| episodes | created_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| episodes | updated_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| episodes | locked_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| episodes | deleted_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| favorites | user_id | users.id | CASCADE | ✅ | ✅ | ✅ |
| favorites | anime_id | anime.id | CASCADE | ✅ | ✅ | ✅ |
| watch_progress | user_id | users.id | CASCADE | ✅ | ✅ | ✅ |
| watch_progress | anime_id | anime.id | CASCADE | ✅ | ✅ | ✅ |
| role_permissions | role_id | roles.id | CASCADE | ✅ | ✅ | ✅ |
| role_permissions | permission_id | permissions.id | CASCADE | ✅ | ✅ | ✅ |
| user_roles | user_id | users.id | CASCADE | ✅ | ✅ | ✅ |
| user_roles | role_id | roles.id | CASCADE | ✅ | ✅ | ✅ |
| user_roles | granted_by | users.id | SET NULL | ✅ | ✅ | ✅ |
| audit_logs | actor_id | users.id | SET NULL | ✅ | ✅ | ✅ |
| **refresh_tokens** | **user_id** | **users.id** | **CASCADE** | ❌ | ✅ | ❌ |

**Total FKs**: 21  
**Matching FKs**: 20/21 (95%)  
**Mismatched**: 1 (refresh_tokens.user_id)

---

## Index Coverage

| Table | Model Indexes | Migration Indexes | Status |
|-------|---------------|-------------------|--------|
| users | email (unique+index) | email (unique only) | ⚠️ Minor |
| anime | title, state, is_deleted | title, state, is_deleted | ✅ |
| releases | anime_id | anime_id | ✅ |
| episodes | release_id, is_deleted | release_id, is_deleted | ✅ |
| favorites | user_id, anime_id | user_id, anime_id | ✅ |
| watch_progress | user_id, anime_id | user_id, anime_id | ✅ |
| roles | name | name | ✅ |
| permissions | name, resource | name, resource | ✅ |
| role_permissions | role_id, permission_id | role_id, permission_id | ✅ |
| user_roles | user_id, role_id | user_id, role_id | ✅ |
| audit_logs | actor_id, actor_type, action, entity_type, entity_id, created_at | Same | ✅ |
| refresh_tokens | user_id, token_hash | user_id, token_hash | ✅ |

**Total index groups**: 12  
**Fully matching**: 11/12 (92%)

---

## Special Types Usage

| Type | Tables Using It | Status |
|------|-----------------|--------|
| UUID | All 12 | ✅ Consistent |
| JSON | anime (genres), audit_logs (before, after) | ✅ Consistent |
| ARRAY | anime (locked_fields), episodes (locked_fields) | ✅ Consistent |
| DateTime(tz=True) | All tables with timestamps | ✅ Consistent |
| Boolean | All tables with flags | ✅ Consistent |

---

## Naming Convention Compliance

| Convention | Tables | Status |
|------------|--------|--------|
| pk_* | 12/12 | ✅ 100% |
| fk_* | 20/20 (in migration) | ✅ 100% |
| ix_* | 39/39 | ✅ 100% |
| uq_* | 5/5 | ✅ 100% |
| ck_* | 0/1 (missing valid_actor_type) | ❌ **CRITICAL** |

---

## FINAL VERDICT

### ❌ INCONSISTENT

**Reason**: 2 CRITICAL issues require immediate fixes before production:
1. Missing security constraint on audit_logs
2. FK mismatch on refresh_tokens

**Recommended Actions**:
1. Create migration 0014 to add CheckConstraint
2. Update RefreshToken model to add ForeignKey
3. Run tests to verify fixes

---

**Full Details**: See `MODEL_SCHEMA_AUDIT_REPORT.md`  
**Executive Summary**: See `AUDIT_EXECUTIVE_SUMMARY.md`
