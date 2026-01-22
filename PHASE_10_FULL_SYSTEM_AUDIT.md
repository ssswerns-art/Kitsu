# AUDIT: FULL SYSTEM REPORT — KITSU PROJECT

**Date**: 2026-01-22  
**Scope**: Backend + Frontend + Integration  
**Python Version**: 3.12  
**Framework**: FastAPI + Next.js 15.3.8

---

## ❌ ISSUE 1 — CRITICAL
**Layer**: Backend / Startup  
**Scope**: Application Lifecycle  
**File**: `backend/app/main.py`  
**Line**: 76-98  
**Impact**: Application crashes with no cleanup on any initialization failure. Partial initialization can leave dangling connections or locks.

**Why this is a real problem**:  
The `lifespan()` function has NO try-except blocks around critical initialization steps (Redis, DB, parser scheduler). If any component fails during startup, the exception propagates uncaught and crashes the application before reaching the `yield` statement. This means cleanup code (lines 94-98) never executes, leaving Redis connections open, database sessions active, and background tasks running orphaned.

**Minimal fix direction**:  
Wrap initialization in try-except block. On failure, perform cleanup (close_redis, stop schedulers) before re-raising. Add finally block to guarantee cleanup runs regardless of success/failure.

---

## ❌ ISSUE 2 — CRITICAL
**Layer**: Backend / Startup  
**Scope**: Redis Integration  
**File**: `backend/app/main.py`  
**Line**: 83-90  
**Impact**: Scheduler can start and attempt operations before Redis connection is actually established, causing silent failures or crashes during first lock acquisition.

**Why this is a real problem**:  
`init_redis()` creates a Redis client object but does NOT verify the connection works. The `RedisClient.connect()` method (infrastructure/redis.py:40-48) creates the client but never calls `ping()` or validates connectivity. The `parser_autoupdate_scheduler.start()` immediately launches a background task that tries to acquire distributed locks (parser/jobs/autoupdate.py:100-106). If Redis is unreachable, startup "succeeds" but the scheduler fails silently on first iteration.

**Minimal fix direction**:  
After `init_redis()`, call `await get_redis()._redis.ping()` to verify connection. Raise clear error if ping fails. Document that Redis must be ready before scheduler starts.

---

## ❌ ISSUE 3 — CRITICAL
**Layer**: Backend / Startup  
**Scope**: Shutdown Sequence  
**File**: `backend/app/main.py`  
**Line**: 94-98  
**Impact**: Resource leaks (connections, tasks) during shutdown if any cleanup step fails.

**Why this is a real problem**:  
Cleanup code has NO exception handling. If `parser_autoupdate_scheduler.stop()` raises an exception (e.g., task cancellation timeout), execution halts and `default_job_runner.stop()` + `close_redis()` never run. This leaves Redis connection open and background tasks potentially running. No logging occurs to indicate which cleanup step failed.

**Minimal fix direction**:  
Wrap each cleanup call in individual try-except blocks. Log exceptions but continue cleanup. Use context manager pattern or explicit finally blocks.

---

## ❌ ISSUE 4 — CRITICAL
**Layer**: Backend / Routers  
**Scope**: Admin Prefix Conflicts  
**File**: `backend/app/api/router.py`, `backend/app/admin/router.py`, `backend/app/parser/admin/router.py`  
**Line**: api/router.py:6,36 | admin/router.py:43 | parser/admin/router.py:49  
**Impact**: Conflicting route prefixes cause ambiguous routing. Multiple routers claim ownership of `/admin/parser/*` namespace.

**Why this is a real problem**:  
Three routers compete for admin namespace:
- `admin/router.py` defines prefix `/admin` with endpoints `/parser/status`, `/parser/restart`, `/parser/sync`
- `parser/admin/router.py` defines prefix `/admin/parser` with `/dashboard`, `/anime_external`, `/settings`
- `api/router.py` includes parser_admin router which creates `/api/admin/parser/*`

This creates THREE potential paths to parser admin functionality: `/admin/parser/*`, `/api/admin/parser/*`, and possibly `/admin/parser/*` duplicated. FastAPI will match the first registered route, making others unreachable. No clear ownership of namespace.

**Minimal fix direction**:  
Consolidate admin routers into single hierarchy. Either: (1) Make parser/admin a sub-router of admin/router, or (2) Keep them separate with distinct non-overlapping prefixes like `/admin` and `/api/parser-admin`. Remove circular import from api/router.py importing parser/admin.

---

## ❌ ISSUE 5 — CRITICAL
**Layer**: Backend / RBAC  
**Scope**: Permission Definitions  
**File**: `backend/app/auth/rbac_contract.py`, `backend/app/admin/contracts/permissions.py`, `backend/app/admin/router.py`  
**Line**: rbac_contract.py:106-113 | admin/router.py:108,164  
**Impact**: Permission checks always fail for ROLES_VIEW and PARSER_VIEW permissions because they're not in the allowed permissions set.

**Why this is a real problem**:  
`admin/router.py` endpoints use `AdminPermission.ROLES_VIEW` (line 108) and `AdminPermission.PARSER_VIEW` (line 164) in permission checks. These enum values exist in `admin/contracts/permissions.py` but are NOT listed in `rbac_contract.ALLOWED_PERMISSIONS` (lines 106-113). When `PermissionService.has_permission()` validates permissions, it checks against this hardcoded list. Since "admin.roles.view" and "admin.parser.view" are missing, validation fails BEFORE database lookup. Result: all requests to `/admin/roles` and `/admin/parser/status` are denied even for super_admin users.

**Minimal fix direction**:  
Add missing permissions to rbac_contract.ALLOWED_PERMISSIONS:
- "admin.roles.view"
- "admin.parser.view"
Ensure all AdminPermission enum values are registered in contract.

---

## ❌ ISSUE 6 — CRITICAL
**Layer**: Backend / Dependencies  
**Scope**: Import-Time Side Effects  
**File**: `backend/app/main.py`, `backend/app/database.py`, `backend/app/config.py`  
**Line**: main.py:50-51 | database.py:8 | config.py:136  
**Impact**: Application fails to import if environment is misconfigured or filesystem lacks permissions.

**Why this is a real problem**:  
Module-level code executes at import time:
- `AVATAR_DIR.mkdir(parents=True, exist_ok=True)` (main.py:51) performs filesystem I/O during module import
- `engine = create_async_engine(...)` (database.py:8) configures database pool at import time
- `settings = Settings.from_env()` (config.py:136) reads environment variables and raises ValueError if missing

If uploads directory doesn't exist and lacks write permissions, OR if DATABASE_URL/SECRET_KEY env vars are missing, the application fails during import BEFORE lifespan runs. This prevents using app instance for testing, introspection, or error handling. Cannot catch startup errors gracefully.

**Minimal fix direction**:  
Move AVATAR_DIR.mkdir() to lifespan startup. Make settings lazy-loaded or raise clear startup error. Consider lazy engine creation pattern.

---

## ❌ ISSUE 7 — HIGH
**Layer**: Backend / Routers  
**Scope**: Path Conflicts  
**File**: `backend/app/api/proxy/search.py`, `backend/app/routers/search.py`, `backend/app/main.py`  
**Line**: proxy/search.py:10 | routers/search.py:17 | main.py:166,172  
**Impact**: Duplicate search endpoints at `/api/search` and `/search` cause confusion. One may shadow the other.

**Why this is a real problem**:  
Two routers define search functionality:
- `api/proxy/search.py` with prefix `/search` included in api_router (prefix `/api`) → final path `/api/search`
- `routers/search.py` with prefix `/search` included directly in app → final path `/search`

Both registered in main.py. FastAPI will match first registered route. If api_router is included first, `/search` endpoint becomes unreachable. No clear indication which is canonical. Frontend may call wrong endpoint.

**Minimal fix direction**:  
Consolidate to single search endpoint. Either remove proxy/search or routers/search. Document which is authoritative. Update frontend if path changes.

---

## ❌ ISSUE 8 — HIGH
**Layer**: Backend / Auth  
**Scope**: Audit Logging  
**File**: `backend/app/admin/dependencies.py`, `backend/app/admin/services/audit_service.py`  
**Line**: admin/dependencies.py:25-52 | admin/services/audit_service.py:67-71  
**Impact**: Admin permission denials are not audited. Critical security events invisible.

**Why this is a real problem**:  
Permission checks in `admin/dependencies.py` (lines 48-52) verify permissions but do NOT log denials. Only successful permission grants trigger audit logs in write endpoints (admin/router.py:288-295). When user attempts unauthorized admin action, `PermissionService.has_permission()` returns False and HTTPException is raised, but no audit record created.

Additionally, `AuditService` only logs to stdlib logger (audit_service.py:67-71), not to database. Fire-and-forget pattern swallows exceptions. No durable audit trail.

**Minimal fix direction**:  
Add audit logging in admin/dependencies.py when permission check fails. Store audit logs in database table with transaction guarantees. Log both grants and denials.

---

## ❌ ISSUE 9 — HIGH
**Layer**: Backend / Data Models  
**Scope**: ORM vs Pydantic Mismatch  
**File**: `backend/app/models/episode.py`, `backend/app/schemas/episode.py`  
**Line**: models/episode.py:25-26 | schemas/episode.py:17-22  
**Impact**: Frontend expects fields that backend doesn't return. Causes client-side defaults and confusion.

**Why this is a real problem**:  
Episode model has fields `available_translations` and `available_qualities` (JSON arrays) that are NOT included in `EpisodeListItem` or `EpisodeRead` schemas. Frontend queries for episodes expect these fields. When backend returns episodes without them, frontend mappers hardcode empty arrays or defaults.

Similarly, frontend expects `isFiller: boolean` field but Episode model has no such column. Frontend hardcodes to `false`.

**Minimal fix direction**:  
Add missing fields to Episode schemas (available_translations, available_qualities). Either add isFiller column to model or remove from frontend expectations. Sync schema with actual model fields.

---

## ❌ ISSUE 10 — HIGH
**Layer**: Backend / Data Models  
**Scope**: Unique Constraint Limitation  
**File**: `backend/app/models/refresh_token.py`  
**Line**: 20  
**Impact**: Users cannot have multiple active sessions (e.g., mobile + desktop). Session on one device invalidates others.

**Why this is a real problem**:  
RefreshToken model has `UniqueConstraint("user_id")` allowing only ONE refresh token per user. When user logs in on second device, first device's session is implicitly invalidated (token revoked or deleted). No explicit multi-session support. Users get logged out unexpectedly when using multiple devices.

**Minimal fix direction**:  
Remove unique constraint on user_id. Allow multiple refresh tokens per user. Add session_id or device_id to track individual sessions. Update logout logic to revoke specific session, not all user sessions.

---

## ⚠️ ISSUE 11 — MEDIUM
**Layer**: Backend / Startup  
**Scope**: Background Tasks  
**File**: `backend/app/parser/jobs/autoupdate.py`, `backend/app/main.py`  
**Line**: autoupdate.py:42-50,90-122 | main.py:90  
**Impact**: Scheduler background task can fail silently without application awareness.

**Why this is a real problem**:  
`parser_autoupdate_scheduler.start()` creates background task but doesn't await it or monitor for exceptions. Task runs in `_loop()` with generic exception handler (line 119-122) that logs errors but continues sleeping. If scheduler fails on first iteration, application startup completes successfully but autoupdate never runs.

No health check endpoint reports scheduler status. No metrics on successful/failed runs.

**Minimal fix direction**:  
Add task exception monitoring. Expose scheduler health in `/health` endpoint. Consider making scheduler failures non-fatal but visible in monitoring.

---

## ⚠️ ISSUE 12 — MEDIUM
**Layer**: Backend / Dependencies  
**Scope**: Database Session Lifetime  
**File**: `backend/app/dependencies.py`  
**Line**: 32-34  
**Impact**: 51 endpoints use `Depends(get_db)` creating independent sessions. Potential inconsistent reads within single request.

**Why this is a real problem**:  
`get_db()` dependency yields new AsyncSession for each injection point. If single request handler has multiple `Depends(get_db)` parameters, each gets separate session. These sessions may have different transaction isolation or read inconsistencies if database changes mid-request.

No documentation on session scope or transaction boundaries.

**Minimal fix direction**:  
Use request-scoped session. Inject single session per request and reuse. Document transaction boundaries clearly. Consider using middleware or dependency override.

---

## ⚠️ ISSUE 13 — MEDIUM
**Layer**: Backend / Auth  
**Scope**: Legacy RBAC Helpers  
**File**: `backend/app/auth/helpers.py`  
**Line**: 36-49  
**Impact**: Legacy permission checks bypass modern contract validation.

**Why this is a real problem**:  
`require_permission()` and `require_any_permission()` use static `rbac.resolve_permissions(role)` hardcoded mapping instead of database lookups. This bypasses `PermissionService` and contract validation. Permissions granted here may not match database state. No audit logging. Used in deprecated endpoints but still callable.

**Minimal fix direction**:  
Mark helpers as deprecated with warnings. Migrate all usages to `require_admin_permission()` pattern. Remove legacy helpers in next major version.

---

## ⚠️ ISSUE 14 — MEDIUM
**Layer**: Frontend / Architecture  
**Scope**: Hydration Warnings  
**File**: `frontend/app/layout.tsx`, `frontend/components/*.tsx`  
**Line**: Multiple locations  
**Impact**: 9 instances of `suppressHydrationWarning` indicate unresolved SSR/CSR mismatches.

**Why this is a real problem**:  
Multiple components use `suppressHydrationWarning` prop to hide React hydration errors. This indicates server-rendered HTML doesn't match client-rendered output. Common causes: date/time formatting, theme detection, auth state checks.

Suppressing warnings doesn't fix underlying issue. Can cause visual glitches, doubled event handlers, or inconsistent state.

**Minimal fix direction**:  
Identify root cause of each hydration mismatch. Use `useEffect` hooks for client-only rendering. Ensure server and client render same initial state. Remove suppressHydrationWarning after fixing causes.

---

## ⚠️ ISSUE 15 — MEDIUM
**Layer**: Frontend / Data  
**Scope**: Error Handling  
**File**: `frontend/hooks/use-watch-progress.ts`, `frontend/query/*.ts`  
**Line**: use-watch-progress.ts:133-137,204-206  
**Impact**: Try-catch in hooks bypasses error boundary contract. Silent failures in UI.

**Why this is a real problem**:  
`useWatchProgress` hook has direct try-catch blocks catching errors from mutations and logging them. This violates error boundary policy (lib/error-boundary-policy.ts) which expects unhandled errors to propagate to error boundaries.

Result: Watch progress mutations can fail silently. User sees no error message. No retry prompts. Error logged to console but not displayed.

**Minimal fix direction**:  
Remove try-catch from hooks. Let errors propagate to error boundaries. Use error boundary policy to classify errors. Display user-friendly messages.

---

## ⚠️ ISSUE 16 — MEDIUM
**Layer**: Frontend / Architecture  
**Scope**: Protected Routes Missing  
**File**: `frontend/app/admin/*`, `frontend/middleware.ts`  
**Line**: N/A - Missing implementation  
**Impact**: Admin pages not protected by middleware. Anyone can access admin UI.

**Why this is a real problem**:  
No Next.js middleware guards admin routes. Users can navigate to `/admin/*` pages without authentication. RBAC checks happen at API level, but UI is exposed. Users see admin interface, attempt actions, then get 403 from backend.

Better UX: redirect to login before showing admin UI. Prevents confusion and unauthorized access attempts.

**Minimal fix direction**:  
Add middleware.ts checking auth for `/admin/*` routes. Redirect to `/login` if not authenticated. Check role and redirect if insufficient permissions. Show appropriate error messages.

---

## ⚠️ ISSUE 17 — MEDIUM
**Layer**: Integration  
**Scope**: Response Structure Mismatch  
**File**: `frontend/types/anime-details.ts`, `backend/app/schemas/anime.py`, `frontend/mappers/anime.mapper.ts`  
**Line**: anime-details.ts:17-32 | anime.py:15-24 | anime.mapper.ts:232-242  
**Impact**: Frontend expects nested Season/Release data with poster field that backend doesn't return.

**Why this is a real problem**:  
Frontend type `IAnimeDetails.seasons` expects array of `Season` objects with `poster: string` field. Backend `ReleaseListItem` schema has no poster field. Frontend mapper (anime.mapper.ts:240) hardcodes `PLACEHOLDER_POSTER` for all seasons.

Result: All season posters show placeholder. Database may have poster data in Anime table but not in Release. Frontend cannot display actual posters.

**Minimal fix direction**:  
Add poster field to ReleaseRead/ReleaseListItem schema. Populate from parent Anime poster or dedicated Release poster column. Update mapper to use actual data.

---

## ⚠️ ISSUE 18 — MEDIUM
**Layer**: Integration  
**Scope**: Episodes Count Mismatch  
**File**: `frontend/query/get-anime-details.ts`, `backend/app/schemas/anime.py`  
**Line**: get-anime-details.ts:96 | anime.py:15-24  
**Impact**: Frontend hardcodes episodes count to `{sub: 0, dub: 0}`. No actual episode count displayed.

**Why this is a real problem**:  
Frontend expects `IAnime.episodes: { sub: number | null, dub: number | null }` in anime details response. Backend `AnimeRead` schema has NO episodes field. Frontend mapper hardcodes to `{sub: 0, dub: 0}` (get-anime-details.ts:96).

Users cannot see how many episodes exist for an anime. Makes navigation difficult. Episode count likely available in database but not exposed via API.

**Minimal fix direction**:  
Add episodes field to AnimeRead schema. Compute from related Episode records grouped by translation type. Return actual counts.

---

## ⚠️ ISSUE 19 — MEDIUM
**Layer**: Integration  
**Scope**: Error Format Mismatch  
**File**: `frontend/lib/api-errors.ts`, `backend/app/errors.py`, `backend/app/main.py`  
**Line**: api-errors.ts:263-314 | errors.py:78-83 | main.py:213-244  
**Impact**: Frontend error handlers don't parse backend error codes. Generic error messages shown to users.

**Why this is a real problem**:  
Backend returns error responses with structure `{ error: { code: string, message: string, details: any } }` (errors.py:78-83). Frontend `normalizeApiError()` function (api-errors.ts:263-314) doesn't extract the `code` field from response body.

When backend returns 400 with code "VALIDATION_ERROR", frontend treats as generic network error. User sees "Request failed" instead of specific validation message. Backend error codes not leveraged in frontend error handling.

**Minimal fix direction**:  
Update normalizeApiError to extract error.code from response body. Map backend error codes to frontend error types. Display specific messages based on code.

---

## 🟡 ISSUE 20 — TECH DEBT
**Layer**: Backend / Routers  
**Scope**: Write Endpoint Stubs  
**File**: `backend/app/admin/router.py`  
**Line**: 284,322,363,399,442  
**Impact**: All admin write endpoints are TODOs with no actual database mutations.

**Why this is a real problem**:  
Five admin write endpoints exist with full permission checks and audit logging but NO actual functionality:
- `POST /admin/users/{user_id}/roles` - TODO: Implement database logic
- `POST /admin/roles/assign` - TODO: Implement bulk assignment
- `POST /admin/parser/restart` - TODO: Implement restart logic
- `POST /admin/parser/sync` - TODO: Implement sync trigger
- `POST /admin/system/maintenance` - TODO: Implement maintenance mode

These endpoints pass permission checks and log audit events but do nothing. Can confuse developers and operators. Incomplete feature implementation.

**Minimal fix direction**:  
Either implement TODOs or remove stub endpoints. If keeping stubs for future work, return 501 Not Implemented status. Document incomplete state clearly.

---

## 🟡 ISSUE 21 — TECH DEBT
**Layer**: Backend / Models  
**Scope**: Missing Schemas  
**File**: `backend/app/models/user_role.py`, `backend/app/models/role_permission.py`, `backend/app/schemas/`  
**Line**: N/A - Missing files  
**Impact**: No Pydantic schemas for UserRole and RolePermission models. Inconsistent API contracts.

**Why this is a real problem**:  
UserRole and RolePermission junction tables have no Pydantic schemas. Cannot expose role assignments or permission grants via API consistently. Endpoints manually construct dictionaries instead of using validated schemas.

Makes API documentation incomplete. No OpenAPI spec for role/permission management.

**Minimal fix direction**:  
Create UserRoleRead, UserRoleCreate schemas. Create RolePermissionRead schema. Use in admin endpoints for consistent responses.

---

## 🟡 ISSUE 22 — TECH DEBT
**Layer**: Frontend / State  
**Scope**: Store Provider Hierarchy  
**File**: `frontend/providers/store-provider.tsx`, `frontend/app/layout.tsx`  
**Line**: store-provider.tsx:1-20 | layout.tsx:25-45  
**Impact**: Nested provider hierarchy adds unnecessary React context layers.

**Why this is a real problem**:  
Provider tree: StoreProvider → AuthStoreProvider → AnimeStoreProvider. Each creates React context. Anime store is non-persistent and could be plain React state instead of Zustand store.

Adds re-render overhead. Complex provider nesting makes debugging difficult. Auth store needs persistence but Anime store doesn't justify Zustand.

**Minimal fix direction**:  
Evaluate if Anime store needs Zustand or can be useState. Flatten provider hierarchy if possible. Document provider dependencies.

---

## 🟡 ISSUE 23 — TECH DEBT
**Layer**: Integration  
**Scope**: Duplicate Validation  
**File**: `frontend/query/get-search-results.ts`, `backend/app/routers/search.py`  
**Line**: get-search-results.ts:12-22 | search.py:18-27  
**Impact**: Search validation logic duplicated on frontend and backend. Can drift out of sync.

**Why this is a real problem**:  
Frontend validates search query length client-side (minimum 2 characters). Backend also validates and returns 400 Bad Request for short queries. Same validation logic in two places.

If validation rules change (e.g., minimum 3 characters), must update both. Risks inconsistency. Better to have single source of truth.

**Minimal fix direction**:  
Remove frontend validation or make it mirror backend contract. Consider shared validation schema if using TypeScript code generation from OpenAPI. Document validation rules in API contract.

---

## 🟡 ISSUE 24 — TECH DEBT
**Layer**: Backend / Dependencies  
**Scope**: Circular Import Structure  
**File**: `backend/app/api/router.py`, `backend/app/parser/admin/router.py`  
**Line**: api/router.py:6  
**Impact**: Parser admin router imported into api router creates coupling. Reorganization difficult.

**Why this is a real problem**:  
`api/router.py` imports `parser/admin/router` which may import other api modules. Creates circular dependency risk. Makes parser module dependent on api module placement.

Better architecture: register routers independently in main.py. Avoid cross-module router imports.

**Minimal fix direction**:  
Remove parser_admin import from api/router.py. Register parser/admin/router directly in main.py alongside api_router. Decouple modules.

---

## 🟡 ISSUE 25 — TECH DEBT
**Layer**: Backend / Routers  
**Scope**: Internal Router Wrappers  
**File**: `backend/app/api/internal/favorites.py`, `backend/app/api/internal/watch.py`  
**Line**: favorites.py:1-6 | watch.py:1-6  
**Impact**: Internal routers are empty wrappers that include base routers with no modifications.

**Why this is a real problem**:  
Files `api/internal/favorites.py` and `api/internal/watch.py` create new routers with no prefix/tags, then include base routers (`routers/favorites.router` and `routers/watch.router`). No additional logic, middleware, or modifications.

Adds indirection without value. Makes router registration path unclear. Harder to trace route definitions.

**Minimal fix direction**:  
Remove internal router wrappers. Include base favorites/watch routers directly in api/router.py or main.py. Simplify router structure.

---

## 🟡 ISSUE 26 — TECH DEBT
**Layer**: Frontend / Architecture  
**Scope**: External API Proxy  
**File**: `frontend/external/proxy/proxy.adapter.ts`, `frontend/query/get-episode-data.ts`, `frontend/query/get-episode-servers.ts`  
**Line**: Various  
**Impact**: Episode video sources and servers fetched from external proxy, not backend API.

**Why this is a real problem**:  
Frontend calls `fetchEpisodeSources()` and `fetchEpisodeServers()` which go directly to external anime scraping API (proxy.adapter.ts), bypassing backend. Backend has `/episodes` endpoint but doesn't provide video sources.

This creates split responsibility: metadata from backend, video from external. If external API changes or goes down, video playback breaks with no backend fallback. Backend cannot cache or validate video sources.

**Minimal fix direction**:  
Proxy external API calls through backend. Backend fetches from external API, validates, caches results. Frontend only calls backend endpoints. Centralizes external API integration.

---

## 🟡 ISSUE 27 — TECH DEBT
**Layer**: Backend / Config  
**Scope**: Settings Validation  
**File**: `backend/app/config.py`  
**Line**: 28-133  
**Impact**: Config validation happens at module import time. Application cannot start with missing env vars even for testing.

**Why this is a real problem**:  
`settings = Settings.from_env()` at line 136 executes during module import. Raises ValueError if SECRET_KEY, ALLOWED_ORIGINS, or DATABASE_URL missing. Makes unit testing difficult - tests fail if env vars not set.

Cannot import config module to inspect settings structure without full environment.

**Minimal fix direction**:  
Make settings lazy-loaded or use dependency injection. Allow test environments to override settings. Consider separating validation from import.

---

## ✅ SAFE / STABLE AREAS

### Backend:
- **Error handling** - Comprehensive exception handlers with proper logging and error codes
- **CORS middleware** - Properly configured with OPTIONS preflight handling
- **Database connection pooling** - Well-configured with pre-ping and recycle settings
- **Token validation** - JWT access/refresh token flow correctly implemented
- **SQLAlchemy models** - Proper column types, constraints, and relationships
- **Pydantic schemas** - Type-safe request/response validation for most endpoints
- **Health endpoint** - Lightweight health check with database connectivity test
- **Logging** - Structured logging with appropriate levels

### Frontend:
- **React Query integration** - Proper caching and retry policies for API calls
- **Auth store** - Persistent authentication state with SSR-safe hydration
- **Token refresh** - Deduplication and automatic refresh on 401 errors
- **Error boundary policy** - Clear classification of errors (contract/internal/external)
- **RBAC client-side** - Role and permission hooks for UI access control
- **Theme provider** - Dark/light mode with next-themes
- **TypeScript types** - Comprehensive type definitions for anime/episodes

### Integration:
- **Auth endpoints** - Login/register/refresh/logout contracts match frontend expectations
- **Anime list endpoint** - `/anime` response correctly mapped to frontend types
- **Episode list endpoint** - `/episodes` by release_id works correctly
- **Search endpoint** - `/search/anime` returns expected format
- **CORS configuration** - Backend allows configured frontend origins

---

## SUMMARY BY LAYER

### BACKEND ISSUES
- **CRITICAL**: 6 issues (startup lifecycle, Redis init, cleanup, router conflicts, RBAC permissions, import-time side effects)
- **HIGH**: 4 issues (path conflicts, audit logging, ORM mismatches, unique constraints)
- **MEDIUM**: 3 issues (background tasks, session lifetime, legacy helpers)
- **TECH DEBT**: 7 issues (write stubs, missing schemas, circular imports, wrappers, config validation)

### FRONTEND ISSUES
- **MEDIUM**: 3 issues (hydration warnings, error handling in hooks, missing protected routes)
- **TECH DEBT**: 2 issues (store hierarchy, external API proxy)

### INTEGRATION ISSUES
- **MEDIUM**: 3 issues (response structure mismatch, episode count hardcoded, error format mismatch)
- **TECH DEBT**: 1 issue (duplicate validation)

---

## PRIORITY RECOMMENDATIONS

### IMMEDIATE (Before Production):
1. Fix startup exception handling in lifespan (ISSUE 1, 2, 3)
2. Resolve admin router prefix conflicts (ISSUE 4)
3. Add missing RBAC permissions to contract (ISSUE 5)
4. Move import-time side effects to startup (ISSUE 6)
5. Implement protected routes middleware (ISSUE 16)

### SHORT TERM (Next Sprint):
1. Consolidate search endpoints (ISSUE 7)
2. Add audit logging for denials (ISSUE 8)
3. Fix Episode schema missing fields (ISSUE 9)
4. Update RefreshToken unique constraint (ISSUE 10)
5. Fix hydration warnings (ISSUE 14)
6. Add error code extraction in frontend (ISSUE 19)

### MEDIUM TERM (Next Quarter):
1. Implement or remove admin write stubs (ISSUE 20)
2. Create missing junction table schemas (ISSUE 21)
3. Refactor router structure (ISSUE 24, 25)
4. Proxy external API through backend (ISSUE 26)
5. Add episode counts to anime details (ISSUE 18)

### REFACTORING (Future):
1. Lazy-load settings (ISSUE 27)
2. Simplify store provider hierarchy (ISSUE 22)
3. Deprecate legacy RBAC helpers (ISSUE 13)
4. Consolidate validation logic (ISSUE 23)

---

**END OF AUDIT**
