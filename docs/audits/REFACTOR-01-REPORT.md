# REFACTOR-01 REPORT: Полный архитектурный и технический аудит проекта

**TASK ID:** REFACTOR-01  
**TITLE:** Полный архитектурный и технический аудит проекта (БЕЗ реализации)  
**ДАТА АУДИТА:** 2026-01-21  
**СТАТУС:** ✅ COMPLETE  
**ЦЕЛЕВАЯ ПЛАТФОРМА:** FastAPI + Python 3.12 + PostgreSQL + Next.js

---

## A. РЕАЛЬНАЯ ТЕКУЩАЯ АРХИТЕКТУРА ПРОЕКТА

### A.1. Общая структура

```
kitsu/
├── backend/           # FastAPI (Python 3.12)
│   ├── app/
│   │   ├── api/           # Роутеры (admin, proxy, internal)
│   │   ├── routers/       # Публичные API эндпоинты
│   │   ├── services/      # Бизнес-логика
│   │   ├── use_cases/     # Доменная логика (DDD pattern)
│   │   ├── crud/          # Data access layer
│   │   ├── models/        # SQLAlchemy ORM модели
│   │   ├── domain/ports/  # Абстрактные интерфейсы (DDD)
│   │   ├── parser/        # Внешние интеграции (Shikimori, Kodik)
│   │   ├── auth/          # RBAC, authentication, enforcement
│   │   ├── schemas/       # Pydantic validation models
│   │   └── background/    # In-process job queue
│   ├── alembic/       # Database migrations
│   └── tests/         # 33 test files
├── frontend/          # Next.js 15 (App Router)
│   ├── app/           # Next.js страницы
│   ├── components/    # React UI компоненты
│   ├── lib/           # API клиент, утилиты
│   └── store/         # Zustand state management
└── docs/              # Архитектурная документация
```

### A.2. Backend архитектура (FastAPI)

**Стек технологий:**
- Python 3.12 (requires-python = ">=3.12")
- FastAPI 0.115.5
- SQLAlchemy 2.0.36 (async)
- Pydantic 2.9
- PostgreSQL (asyncpg 0.29.0)
- Alembic 1.13.2

**Архитектурные слои:**
1. **API Layer** (роутеры)
   - `/api/admin/*` — административные операции
   - `/api/proxy/*` — прокси к HiAnime, AniList
   - `/api/internal/*` — бизнес-операции (favorites, watch progress)
   - Публичные роутеры: `/anime`, `/auth`, `/episodes`, `/search`

2. **Service Layer**
   - `services/admin/anime_service.py` — управление аниме
   - `services/admin/permission_service.py` — RBAC enforcement
   - `services/audit/` — audit logging
   - `services/statistics/` — аналитика

3. **Use Cases Layer** (Domain-Driven Design)
   - `use_cases/auth/` — register_user, login_user, refresh_token
   - `use_cases/favorites/` — add_favorite, remove_favorite
   - `use_cases/watch/` — submit_watch_progress

4. **CRUD Layer**
   - Функции: `get_anime_by_id()`, `get_anime_list()`
   - Классы-репозитории: `FavoriteRepository`, `WatchProgressRepository`
   - **Дублирование:** Один и тот же функционал в двух стилях

5. **Domain Ports** (абстракции)
   - `UserPort`, `TokenPort`, `FavoritePort`, `WatchProgressPort`
   - Dependency injection через FastAPI Depends()

6. **Parser Layer**
   - Интеграции: Shikimori (каталог), Kodik (эпизоды)
   - Orchestration: `ParserWorker`, `ParserScheduler`
   - Staging tables: `anime_external`, `parser_jobs`, `parser_settings`

**Паттерны:**
- ✅ Async/await (100% async routes, async SQLAlchemy)
- ✅ Dependency Injection (FastAPI Depends)
- ✅ Domain-Driven Design (ports, use_cases)
- ⚠️ Смешанные стили CRUD (функции + классы)
- ⚠️ Прямой доступ к БД из некоторых роутеров

### A.3. Frontend архитектура (Next.js)

**Стек технологий:**
- Next.js 15.3.8 (App Router)
- React 18.3
- React Query 3.39.3 (query cache)
- Zustand 5.0.3 (state management)
- Axios 1.7.7 (HTTP client)
- TailwindCSS + Radix UI
- PocketBase 0.25.2 (auth/storage)

**Архитектурные паттерны:**
- ✅ Centralized API client с interceptors
- ✅ Contract validation (fail-fast на несоответствие API)
- ✅ SSR/CSR boundary guards (lifecycle-guards)
- ✅ Query cache (5min stale, 10min cache)
- ✅ Auth token refresh с deduplication
- ⚠️ Hydration tracking (defensive pattern против прошлых проблем)

### A.4. Database архитектура (PostgreSQL)

**ORM модели:**
- `User`, `Role`, `Permission`, `UserRole`, `RolePermission`
- `Anime`, `Episode`, `Release`, `Favorite`, `WatchProgress`
- `AuditLog`, `RefreshToken`
- `ParserSettings`, `ParserJob`, `ParserJobLog`
- `AnimeExternal`, `AnimeSchedule`, `AnimeEpisodesExternal`

**Миграции:**
- 13 Alembic миграций (0001-0013)
- Миграции на soft delete, RBAC, parser tables, audit logging

**Особенности:**
- Soft delete (`is_deleted` flag в Anime/Episode)
- Audit trail (`created_by`, `updated_by`, `deleted_by`, `locked_by`)
- UUID primary keys
- Async sessions (`expire_on_commit=False`)

### A.5. Security & RBAC

**Текущая реализация:**
- **Старая система:** `auth/rbac.py` (DEPRECATED, legacy)
  - Hardcoded `ROLE_PERMISSIONS` dict
  - `require_permission()` helper
  - Используется в `/parser/admin/router.py` (16+ endpoints)

- **Новая система:** `auth/rbac_contract.py` + `services/admin/permission_service.py`
  - Database-driven permissions
  - Contract validation at import-time
  - Hard invariants (no wildcards, system≠admin permissions)
  - Используется в новых эндпоинтах

- **Enforcement Matrix:** `auth/enforcement_matrix.py`
  - Вызывает deprecated `require_permission()`
  - Смешивает старые и новые permission names

**Audit Logging:**
- `models/audit_log.py` — ORM модель
- `services/audit/audit_service.py` — сервис логирования
- `actor_type` validation: user, admin, system
- Логирование permission denials, login attempts

---

## B. НЕСООТВЕТСТВИЯ ЦЕЛЕВОЙ ПЛАТФОРМЕ

### B.1. Python 3.12 Compatibility

**✅ Соответствует:**
- `pyproject.toml`: `requires-python = ">=3.12"`
- Использование современных typing hints (`str | None`, `list[str]`)
- 23 файла используют `from __future__ import annotations`
- Async patterns совместимы с Python 3.12

**⚠️ Частичное соответствие:**
- 10 файлов всё ещё используют legacy typing:
  - `from typing import Optional, Union, List, Dict, Tuple`
  - Файлы: `api/proxy/*.py`, `parser/*.py`, `player/*.py`, `security/token_inspection.py`
- Это не ошибки, но не соответствует Python 3.12 best practices

**❌ Проблемные паттерны:**
- `parser/sources/_http.py`: `asyncio.run()` в sync context
  - Создаёт новый event loop или запускает в thread
  - Используется для bridge sync/async в parser sources
  - Потенциальные проблемы с deadlocks

### B.2. FastAPI Best Practices

**✅ Соответствует:**
- Dependency injection через Depends()
- Async route handlers
- Pydantic v2 validation
- Error handling middleware
- CORS configuration

**❌ Не соответствует:**
- Прямой доступ к БД из некоторых роутеров
  - `routers/anime.py`: вызывает `crud.get_anime_list(db)` напрямую
  - Best practice: использовать service layer
- Смешанные стили (некоторые роутеры через services, другие через CRUD)
- Response models не всегда используются (некоторые эндпоинты возвращают dict)

### B.3. PostgreSQL Integration

**✅ Соответствует:**
- SQLAlchemy 2.0 async
- Alembic migrations
- Connection pooling
- Foreign keys, indexes

**❌ Проблемы:**
- Отсутствует `ForeignKey` в `RefreshToken.user_id` (только в миграции, не в модели)
- Отсутствуют составные индексы на часто используемых комбинациях
- N+1 queries в admin list endpoints (нет eager loading)
- Soft delete фильтрация не консистентна (не все CRUD фильтруют `is_deleted`)

### B.4. Next.js Alignment

**✅ Соответствует:**
- Next.js 15 (latest)
- App Router (modern)
- React 18
- TypeScript 5

**⚠️ Потенциальные несоответствия:**
- PocketBase integration (0.25.2) — зачем, если backend FastAPI?
- `aniwatch` package (2.24.3) — дубль с backend proxy?
- Defensive patterns (hydration guards) — признак прошлых проблем

---

## C. ПОЛНЫЙ СПИСОК ПРОБЛЕМ

### 🔴 CRITICAL (безопасность, данные, масштабирование)

#### C.1. 🔴 RBAC Permission System Mismatch
**Проблема:** Parser admin router использует deprecated `require_permission()` с legacy permission format (`"admin:parser.logs"`), но новый контракт определяет их как `"admin.parser.logs"` (dots, not colons).

**Расположение:**
- `/parser/admin/router.py` (16+ endpoints)
- `/auth/helpers.py` (deprecated `require_permission()`)
- `/auth/rbac.py` (deprecated `resolve_permissions()`)

**Риск:**
- ~13 sensitive endpoints могут не enforce permission checks корректно
- Hardcoded fallback в deprecated `ROLE_PERMISSIONS` может silently fail
- Parser operations (run_parser_sync, update_settings, emergency_stop) под угрозой

**Затронутые эндпоинты:**
```python
# parser/admin/router.py
@require_permission("admin:parser.logs")     # WRONG FORMAT
@require_permission("admin:parser.settings") # WRONG FORMAT
@require_permission("admin:parser.sync")     # WRONG FORMAT
```

**Последствия:** Privilege escalation, unauthorized parser control.

---

#### C.2. 🔴 Enforcement Matrix Uses Deprecated System
**Проблема:** `auth/enforcement_matrix.py` вызывает deprecated `require_permission()` с новыми permission names, но deprecated resolver использует hardcoded dict без этих permissions.

**Расположение:**
- `auth/enforcement_matrix.py` (lines 19-21)

**Риск:**
- Enforcement matrix permissions silently fail
- Security decisions based on incorrect permission checks

---

#### C.3. 🔴 Missing actor_type Context Validation
**Проблема:** `dependencies.py` извлекает user из JWT, но никогда не устанавливает/валидирует `actor_type`. Parser admin endpoints hardcode `actor_type="user"`, но system-generated content должен использовать `actor_type="system"`.

**Расположение:**
- `dependencies.py` (get_current_user)
- `parser/admin/router.py` (все эндпоинты)

**Риск:**
- Parser operations (system processes) логируются как user actions
- Audit trail integrity broken
- User может pass `actor_type="system"` без validation
- Privilege escalation через actor_type injection

---

#### C.4. 🔴 N+1 Query Vulnerability in Admin Lists
**Проблема:** `AnimeAdminService.list_anime()` возвращает список Anime без eager loading relationships. При сериализации доступ к `created_by`, `updated_by`, `locked_by` триггерит 4 дополнительных запроса на каждое аниме.

**Расположение:**
- `services/admin/anime_service.py` (line 67)
- Все admin list endpoints

**Риск:**
- Performance degradation на больших списках
- Database connection exhaustion
- DoS potential через large page sizes

---

#### C.5. 🔴 Missing Foreign Key Constraint in RefreshToken
**Проблема:** `RefreshToken` model не объявляет `ForeignKey` на `user_id`, хотя миграция 0005 корректно создаёт его в БД.

**Расположение:**
- `models/refresh_token.py` (line 18)

**Риск:**
- ORM не enforce referential integrity
- Orphaned tokens при delete user
- Cascade delete не работает на ORM уровне
- Data consistency issues

---

#### C.6. 🔴 Incomplete Audit Logging on Critical Operations
**Проблема:** Parser admin endpoints НЕ вызывают `AuditService` для логирования операций:
- `publish_anime_external()` — no audit log
- `update_settings()` — no audit log
- `toggle_parser_mode()` — documented to use audit, но implementation missing

**Расположение:**
- `parser/admin/router.py` (multiple endpoints)

**Риск:**
- Critical configuration changes bypass audit trail
- Невозможно определить кто/когда изменил parser settings
- Compliance violations (no audit trail)

---

#### C.7. 🔴 Parser Retry Logic Doesn't Handle 429
**Проблема:** `RateLimitedRequester._get_json()` retries только на `httpx.RequestError`, но не на HTTP 429 (rate limit exceeded).

**Расположение:**
- `parser/sources/_http.py`

**Риск:**
- API rate-limiting не детектируется
- External service может заблокировать IP
- Cascading failures при repeated 429s
- No circuit breaker pattern

---

#### C.8. 🔴 No Circuit Breaker for API Failures
**Проблема:** Parser worker НЕ имеет circuit breaker pattern для repeated API failures. При повторных ошибках продолжает retry без backoff.

**Расположение:**
- `parser/worker.py`
- `parser/sources/_http.py`

**Риск:**
- Cascading delays при API downtime
- Database connection exhaustion от failed jobs
- Thundering herd problem при recovery

---

### 🟠 HIGH (серьёзный техдолг)

#### C.9. 🟠 CRUD Layer Duplication
**Проблема:** CRUD layer имеет ДВА стиля для одного и того же функционала:
- Standalone functions: `get_anime_by_id()`, `get_anime_list()`
- Class-based repositories: `FavoriteRepository`, `WatchProgressRepository`

**Расположение:**
- `crud/anime.py` (functions)
- `crud/favorite.py` (class)
- `crud/watch_progress.py` (class)

**Риск:**
- Сложность поддержки (два пути для одной цели)
- Новые разработчики не знают, какой стиль использовать
- Тестирование дублируется
- Refactoring затруднён

**Причина:** Incremental migration от functions к ports/repositories.

---

#### C.10. 🟠 Parser Sources Sync/Async Bridge
**Проблема:** `parser/sources/_http.py` использует `asyncio.run()` для bridge sync/async. Функция `run_sync()` проверяет running loop и создаёт новый или запускает в thread.

**Расположение:**
- `parser/sources/_http.py` (lines 12-36)

**Риск:**
- Deadlocks при неправильном использовании
- Thread creation overhead
- Difficult debugging
- Непредсказуемое поведение в разных contexts

**Причина:** Parser sources изначально sync, backend async.

---

#### C.11. 🟠 Soft Delete Filtering Inconsistency
**Проблема:** `Anime` model имеет `is_deleted` flag, но не все CRUD операции фильтруют его:
- `get_anime_list()` в `crud/anime.py` НЕ фильтрует deleted items
- Только `anime_admin.py` фильтрует `where is_deleted is False`

**Расположение:**
- `crud/anime.py`
- `services/admin/anime_service.py`

**Риск:**
- Users видят deleted content
- Search results включают deleted items
- Business logic может оперировать на deleted data

---

#### C.12. 🟠 Two Background Job Systems
**Проблема:** Проект использует ДВА separate job schedulers:
1. `ParserWorker` (async-driven, DB-controlled)
2. `ParserAutoupdateScheduler` (loop-based)

**Расположение:**
- `parser/worker.py`
- `parser/scheduler.py`

**Риск:**
- Job conflicts если оба active
- Сложность monitoring
- Different failure modes
- Resource competition

---

#### C.13. 🟠 Missing Composite Indexes
**Проблема:** Отсутствуют составные индексы на часто используемых комбинациях:
- `(is_deleted, state)` на `anime` table
- `(user_id, anime_id)` на `watch_progress` (есть unique constraint, но нет отдельного index для queries)
- FK pairs на `RolePermission`, `UserRole`

**Расположение:**
- Database migrations

**Риск:**
- Slow queries на admin list filtering
- Full table scans на soft-delete queries
- Performance degradation с ростом данных

---

#### C.14. 🟠 Session Management Pattern Inconsistency
**Проблема:** Mixed async session patterns:
- Некоторые CRUD методы используют `session.commit()`
- Другие используют только `flush()`
- `RoleRepository.create()` использует `commit()` + `refresh()`, inconsistent с базовым паттерном

**Расположение:**
- `crud/*.py` (различные файлы)
- `dependencies.py` (создаёт multiple AsyncSessionLocal instances)

**Риск:**
- Potential connection leaks
- Unexpected transaction boundaries
- Difficult testing (different isolation levels)

---

#### C.15. 🟠 Direct Router Database Access
**Проблема:** Некоторые роутеры получают `AsyncSession = Depends(get_db)` напрямую и вызывают CRUD functions, минуя service layer.

**Расположение:**
- `routers/anime.py` (line 19: `get_anime_list(db)`)
- Другие публичные роутеры

**Риск:**
- Business logic leaks в presentation layer
- Трудно тестировать
- Нарушение separation of concerns
- Inconsistent с остальной архитектурой (services vs CRUD)

---

#### C.16. 🟠 Legacy Typing Imports
**Проблема:** 10 файлов всё ещё используют legacy typing imports вместо Python 3.10+ builtin generics:
- `from typing import Optional, Union, List, Dict, Tuple`
- Вместо: `str | None`, `list[str]`, `dict[str, Any]`

**Расположение:**
- `api/proxy/*.py`
- `parser/*.py`
- `player/*.py`
- `security/token_inspection.py`

**Риск:**
- Не соответствует Python 3.12 best practices
- Code style inconsistency
- Potential deprecation warnings в Python 3.14+

---

### 🟡 MEDIUM (ухудшение поддержки)

#### C.17. 🟡 Migration vs Model Discrepancies
**Проблема:** Некоторые миграции не отражены в ORM моделях:
- `Permission` model не определяет `resource` как index, но migration 0013 создаёт `ix_permissions_resource`
- `Anime` model missing `title_ru`/`title_en` из migration 0002 (добавлены позже)

**Расположение:**
- `models/permission.py`
- `alembic/versions/0002_*, 0013_*`

**Риск:**
- Model drift от database schema
- Confusion при debugging
- Potential migration conflicts

---

#### C.18. 🟡 Test Isolation Issues
**Проблема:** Тесты используют shared global state:
- `auth_rate_limiter.clear()` в fixture (module-level state)
- Database seeding functions вызываются inside test bodies (`_seed_manual_mode`, `_seed_auto_mode`)
- Hardcoded test data (всегда `id=1` для settings)

**Расположение:**
- `tests/test_auth_rate_limit.py`
- `tests/test_parser_worker.py` (lines 122-175)

**Риск:**
- Flaky tests при parallel execution
- Order dependencies (хотя нет `@pytest.mark.order`)
- ID collisions если tests run out of order

---

#### C.19. 🟡 Duplicated Test Fake Objects
**Проблема:** Fake objects редефинированы per test file:
- `FakeUser`, `FakeUserPort` в `test_auth_use_cases.py`
- `FakeFavorite`, `FakeFavoriteRepository` в `test_favorites_use_cases.py`
- `AsyncSessionAdapter` в 3 разных test files

**Расположение:**
- `tests/test_auth_use_cases.py`
- `tests/test_favorites_use_cases.py`
- `tests/test_parser_*.py`

**Риск:**
- Changes к реальному API не propagate к fakes
- Fakes diverge от real behavior
- Maintenance burden (DRY violation)
- Tests hide real problems

---

#### C.20. 🟡 False Coverage Tests
**Проблема:** Тесты проходят, но не validate поведение:
- Trivial model tests (assert input === output при instantiation)
- Hardcoded constants tests (`test_user_roles_defined` просто assert constants equal themselves)
- Mock call assertions без verification данных

**Расположение:**
- `tests/test_admin_core.py` (lines 32-150)
- `tests/test_rbac_contract.py` (lines 46-54)
- `tests/test_audit_service_security.py` (lines 42-87)

**Риск:**
- False sense of security (high coverage, low value)
- Tests don't catch real bugs
- Maintenance waste

---

#### C.21. 🟡 Async Test Pattern Issues
**Проблема:** Тесты используют problematic async patterns:
- Hard-coded `asyncio.sleep(0.5)` без timeout protection
- `AsyncSessionAdapter` wraps sync `Session` (не true async)
- No concurrent access tests

**Расположение:**
- `tests/test_parser_worker.py` (line 229)
- Fixture definitions в test files

**Риск:**
- Tests fail на slow CI
- Race conditions not tested
- Deadlocks possible под real async load

---

#### C.22. 🟡 Parser Hard-coded Base URLs
**Проблема:** External service URLs hardcoded в source classes:
- `ShikimoriCatalogSource: base_url="https://shikimori.one/api"`
- `KodikEpisodeSource: base_url="https://kodikapi.com"`

**Расположение:**
- `parser/sources/shikimori_catalog.py`
- `parser/sources/kodik_episode.py`

**Риск:**
- Не конфигурируемо per environment
- Testing против real APIs (нет mock endpoints)
- URL changes require code changes

**Митигация:** URLs могут быть overridden через `__init__` params, но не via settings.

---

#### C.23. 🟡 Optional Audit Failure Silently Swallowed
**Проблема:** `PermissionService.require_permission()` line 178 silently swallows audit logging failures: `except Exception: pass`.

**Расположение:**
- `services/admin/permission_service.py` (line 178)

**Риск:**
- If audit service crashes, permission denial goes unlogged
- Compliance violations (missing audit trail)
- Difficult debugging

---

#### C.24. 🟡 Missing Edge Case Tests
**Проблема:** Тесты не покрывают edge cases:
- Invalid state transitions (state → same state, illegal transitions)
- Database connection timeouts
- Concurrent transaction scenarios
- Cascading deletes

**Расположение:**
- `tests/test_anime_management.py`
- Отсутствующие integration tests

**Риск:**
- Edge case bugs в production
- Unexpected behavior при concurrency
- Data corruption scenarios

---

### 🟢 LOW (косметика)

#### C.25. 🟢 `from __future__ import annotations` Inconsistency
**Проблема:** Только 23 из 154 Python files используют `from __future__ import annotations`.

**Расположение:**
- Scattered across codebase

**Риск:**
- Code style inconsistency
- Потенциальные circular import issues при forward references

---

#### C.26. 🟢 Frontend Defensive Patterns
**Проблема:** Frontend имеет defensive patterns (hydration guards, contract assertions), что указывает на прошлые проблемы.

**Расположение:**
- `frontend/lib/lifecycle-guards`
- `frontend/lib/api.ts` (assertErrorHandlingInPolicy)

**Риск:**
- Code smell (fixes симптомов, не причин)
- Potential brittleness (string matching для error boundary)

---

#### C.27. 🟢 PocketBase Integration Unclear
**Проблема:** Frontend использует PocketBase (0.25.2), но backend FastAPI. Зачем два auth systems?

**Расположение:**
- `frontend/package.json`

**Риск:**
- Confusion о том, какой auth используется
- Potential conflicts
- Unused dependency?

---

#### C.28. 🟢 Aniwatch Package Duplication
**Проблема:** Frontend использует `aniwatch` package (2.24.3), но backend уже имеет `/api/proxy/*` для HiAnime.

**Расположение:**
- `frontend/package.json`

**Риск:**
- Duplicate functionality
- Confusion о том, где делать API calls
- Maintenance waste

---

#### C.29. 🟢 Hardcoded Test Constants
**Проблема:** Тесты проверяют hardcoded constants, которые никогда не меняются:
- `test_user_roles_defined()` просто assert `USER_ROLES` is a set
- No behavior validation

**Расположение:**
- `tests/test_rbac_contract.py`

**Риск:**
- Zero value tests
- Waste CI time

---

#### C.30. 🟢 No Comments Policy Unclear
**Проблема:** Нет TODO/FIXME/HACK comments в коде (search returned 0 results), что может означать:
- Отличная code hygiene
- Или недостаток документации inline

**Расположение:**
- Entire codebase

**Риск:**
- Низкий (либо хорошо, либо нейтрально)

---

## D. ПРИЧИНЫ ПРОБЛЕМ

### D.1. Разные ИИ и стили кодирования

**Очевидные признаки:**
1. **CRUD Layer Duplication** (C.9)
   - Старые файлы: функции (`crud/anime.py`)
   - Новые файлы: классы-репозитории (`crud/favorite.py`)
   - Причина: Incremental migration между AI coding sessions

2. **RBAC Systems Mismatch** (C.1, C.2)
   - Deprecated `auth/rbac.py` с legacy permission format
   - Новый `auth/rbac_contract.py` с modern contract
   - Причина: New AI implemented contract, но не migrated старые endpoints

3. **Typing Styles** (C.16, C.25)
   - Старые файлы: `from typing import Optional, List`
   - Новые файлы: Python 3.10+ generics (`str | None`)
   - 23 files с `from __future__ import annotations`, остальные без
   - Причина: Different AI sessions с different style preferences

4. **Test Patterns** (C.19, C.20)
   - Duplicate fake objects per file (не shared fixtures)
   - Trivial tests vs behavioral tests
   - Причина: Different testing philosophies

### D.2. Наследие версий

1. **Python Version Migration**
   - Legacy typing imports остались от Python 3.9/3.10 era
   - Modern code использует 3.12 features
   - `asyncio.run()` sync/async bridge (C.10) — workaround для legacy sync sources

2. **FastAPI/Pydantic Upgrades**
   - Code написан для Pydantic v1, migrated к v2
   - `deprecated="auto"` в `utils/security.py` — artifact от migration

3. **SQLAlchemy 1.4 → 2.0 Migration**
   - Async patterns не везде consistent
   - `expire_on_commit=False` — mitigation от 1.4 era issues
   - Session management inconsistency (C.14)

### D.3. Отсутствие контрактов (изначально)

1. **RBAC Contract**
   - Implemented только недавно (`rbac_contract.py`)
   - Старый код ещё не migrated (C.1, C.2)
   - Enforcement matrix uses deprecated helpers (C.2)

2. **Audit Logging Contract**
   - `AuditService` определён, но не enforcement везде (C.6)
   - Parser endpoints bypass audit logging
   - `actor_type` validation не enforced на application level (C.3)

3. **API Contracts**
   - Frontend имеет defensive contract validation (`ContractError`)
   - Это REACTION на past issues, не preventive measure
   - Hydration guards — workaround для SSR/CSR problems

### D.4. Incremental Development

1. **Domain Ports Migration**
   - Port pattern implemented для `user`, `token`, `favorite`, `watch_progress`
   - НО НЕ для `anime`, `episode`, `release` (всё ещё direct CRUD)
   - Причина: Partial migration

2. **Service Layer Adoption**
   - Новые endpoints используют services
   - Старые endpoints всё ещё direct CRUD (C.15)
   - Inconsistent architecture

3. **Background Jobs**
   - Two separate job systems (C.12)
   - Причина: `ParserWorker` added later, `default_job_runner` уже existed

---

## E. КАРТА РИСКОВ (что нельзя трогать без плана)

### E.1. 🔴 ВЫСОКИЙ РИСК (требует тщательного планирования)

#### E.1.1. RBAC System Migration
**Файлы:**
- `auth/rbac.py` (DEPRECATED)
- `auth/helpers.py` (deprecated `require_permission()`)
- `auth/enforcement_matrix.py`
- `parser/admin/router.py` (16+ endpoints)

**Риск:**
- Breaking change для всех parser admin endpoints
- Potential privilege escalation если migration неправильная
- Требует audit trail migration plan
- Testing всех permission paths

**План миграции требует:**
1. Mapping legacy permissions → new contract permissions
2. Database seeding для новых permissions
3. Incremental migration (one endpoint at a time?)
4. Rollback strategy
5. Testing matrix для всех roles

---

#### E.1.2. CRUD Layer Consolidation
**Файлы:**
- `crud/*.py` (все файлы)
- `domain/ports/*.py`
- `routers/*.py` (все роутеры)
- `services/*.py` (все сервисы)

**Риск:**
- Massive refactoring (затрагивает весь codebase)
- Потенциальные breaking changes для всех API endpoints
- Database transaction boundaries могут измениться
- Testing всего API required

**План миграции требует:**
1. Решение: functions vs classes vs ports
2. Создание migration guide
3. Feature flag strategy для incremental rollout?
4. Comprehensive integration tests

---

#### E.1.3. Parser Sources Async Migration
**Файлы:**
- `parser/sources/*.py`
- `parser/sources/_http.py` (sync/async bridge)
- `parser/worker.py`
- `parser/scheduler.py`

**Риск:**
- Parser может сломаться полностью
- External API integration changes
- Потенциальные rate limit violations при неправильной async impl
- Данные могут быть corrupted if migration fails mid-process

**План миграции требует:**
1. Research: are Shikimori/Kodik APIs async-friendly?
2. Testing plan (staging environment с real APIs?)
3. Rollback strategy (can't rollback published data)
4. Monitoring plan

---

#### E.1.4. Database Schema Changes
**Файлы:**
- `models/*.py`
- `alembic/versions/*.py`
- Весь CRUD layer

**Риск:**
- Data loss при incorrect migrations
- Downtime на production
- Rollback сложность (некоторые migrations irreversible)

**План миграции требует:**
1. Backup strategy
2. Migration testing на staging
3. Rollback plan для каждой migration
4. Zero-downtime migration strategy (если нужно)

---

### E.2. 🟠 СРЕДНИЙ РИСК (можно делать incremental)

#### E.2.1. Service Layer Standardization
**Файлы:**
- `routers/*.py` (некоторые endpoints)
- `services/*.py`

**Риск:**
- Некоторые API endpoints могут сломаться
- Но можно делать one endpoint at a time

**Подход:**
- Incremental migration
- Start с least critical endpoints
- Comprehensive testing на каждом шаге

---

#### E.2.2. Test Quality Improvements
**Файлы:**
- `tests/*.py`

**Риск:**
- Низкий (тесты не влияют на production)
- Но требует time investment

**Подход:**
- Incremental improvements
- Start с critical paths (auth, permissions)
- Refactor test fixtures в `conftest.py`

---

#### E.2.3. Frontend Defensive Patterns Removal
**Файлы:**
- `frontend/lib/lifecycle-guards`
- `frontend/lib/api.ts`

**Риск:**
- Могут вернуться старые проблемы
- НО если root causes fixed, можно удалить

**Подход:**
- Understand WHY defensive patterns added (git history?)
- Fix root causes first
- Then remove defensive code

---

### E.3. 🟢 НИЗКИЙ РИСК (safe refactoring)

#### E.3.1. Typing Modernization
**Файлы:**
- `api/proxy/*.py`
- `parser/*.py`
- `player/*.py`

**Риск:**
- Минимальный (typing не влияет на runtime)

**Подход:**
- Automated refactoring (IDE или script)
- One PR для всех changes

---

#### E.3.2. Dead Code Removal
**Файлы:**
- Trivial tests
- Hardcoded constants tests
- Unused imports

**Риск:**
- Минимальный

**Подход:**
- Automated tools (flake8, pylint, mypy)

---

## F. ОБЩЕЕ ТЕХНИЧЕСКОЕ СОСТОЯНИЕ ПРОЕКТА

### F.1. Оценка по категориям

| Категория | Оценка | Комментарий |
|-----------|--------|-------------|
| **Архитектура** | 🟡 **6/10** | Solid foundation (DDD, ports, services), но inconsistent применение |
| **Безопасность** | 🔴 **4/10** | RBAC migration incomplete, audit logging gaps, actor_type validation missing |
| **Код качество** | 🟡 **6/10** | Modern Python, но mixed styles, duplication |
| **База данных** | 🟡 **7/10** | SQLAlchemy 2.0, migrations OK, но N+1 queries, missing indexes |
| **Тесты** | 🟠 **5/10** | 33 test files, но false coverage, isolation issues |
| **Производительность** | 🟠 **5/10** | N+1 queries, no circuit breaker, potential bottlenecks |
| **Документация** | ✅ **8/10** | Excellent docs (ARCHITECTURE.md, contracts, audits) |
| **DevEx** | 🟡 **6/10** | Docker, migrations, но inconsistent patterns confuse |

### F.2. Strengths (что работает хорошо)

✅ **Архитектурная документация**
- Comprehensive docs в `/docs`
- Contracts для parser, RBAC
- Architecture diagrams

✅ **Modern tech stack**
- Python 3.12
- FastAPI (latest)
- SQLAlchemy 2.0 async
- Pydantic v2
- Next.js 15

✅ **Domain-Driven Design patterns**
- Port/adapter pattern
- Use cases layer
- Clear domain boundaries

✅ **Security foundation**
- RBAC contract design is solid
- Audit logging design is good
- JWT token refresh flow

✅ **Database migrations**
- Alembic setup
- 13 migrations без conflicts
- Good naming conventions

✅ **Frontend architecture**
- Modern Next.js 15
- Query caching
- Contract validation

### F.3. Weaknesses (что требует внимания)

❌ **Incomplete migrations**
- RBAC old→new migration incomplete
- CRUD functions→ports migration partial
- Service layer adoption inconsistent

❌ **Security gaps**
- 16+ endpoints используют deprecated permissions
- Audit logging не везде
- actor_type validation missing

❌ **Performance risks**
- N+1 queries
- No circuit breaker
- Missing composite indexes
- No connection pooling monitoring

❌ **Test quality**
- False coverage (trivial tests)
- Fake objects не shared
- No concurrent tests
- Timing-dependent tests

❌ **Code duplication**
- CRUD layer (functions + classes)
- Test fakes per file
- Background job systems (two separate)

### F.4. Technical Debt Score

**Метрика:**
- 🔴 Critical: 8 issues
- 🟠 High: 8 issues
- 🟡 Medium: 9 issues
- 🟢 Low: 5 issues

**Total:** 30 identified issues

**Weighted Score:**
- Critical × 10 = 80
- High × 5 = 40
- Medium × 2 = 18
- Low × 1 = 5
- **Total: 143 points**

**Technical Debt Level:** 🟠 **HIGH** (requires prioritized remediation)

### F.5. Готовность к production scale

| Критерий | Статус | Комментарий |
|----------|--------|-------------|
| **Security** | 🔴 **NO** | RBAC migration must complete, audit logging gaps |
| **Performance** | 🟠 **PARTIAL** | N+1 queries need fixing, indexes missing |
| **Reliability** | 🟡 **PARTIAL** | No circuit breaker, retry logic incomplete |
| **Observability** | 🟡 **PARTIAL** | Audit logs design OK, но implementation incomplete |
| **Data Integrity** | 🟡 **PARTIAL** | Foreign key missing, soft delete inconsistent |
| **Scalability** | 🟠 **PARTIAL** | Single-process job queue, no connection pooling monitoring |

**Вердикт:** Проект НЕ готов к production scale без устранения 🔴 Critical и 🟠 High issues.

### F.6. Рекомендуемые следующие шаги

**Immediate (P0):**
1. ✅ Завершить RBAC migration (`parser/admin/router.py` → new `PermissionService`)
2. ✅ Добавить `actor_type` validation в `dependencies.py`
3. ✅ Добавить audit logging во все parser admin endpoints
4. ✅ Fix `RefreshToken` foreign key в model
5. ✅ Implement N+1 query fix (eager loading)

**Short-term (P1):**
1. ✅ Add composite indexes (soft delete + state)
2. ✅ Implement circuit breaker для parser sources
3. ✅ Add 429 handling в retry logic
4. ✅ Standardize CRUD layer (выбрать functions OR ports)
5. ✅ Fix soft delete filtering consistency

**Medium-term (P2):**
1. ✅ Consolidate background job systems
2. ✅ Migrate legacy typing imports
3. ✅ Refactor test fakes → shared fixtures
4. ✅ Remove false coverage tests
5. ✅ Add integration tests (auth + parser)

**Long-term (P3):**
1. ✅ Parser sources async migration (if needed)
2. ✅ Frontend defensive patterns removal (after root causes fixed)
3. ✅ Standardize service layer usage (all routers)
4. ✅ Database schema consistency audit
5. ✅ Performance monitoring implementation

---

## ЗАКЛЮЧЕНИЕ

**Проект Kitsu находится в состоянии активной эволюции.**

**Positive:**
- ✅ Solid architectural foundation (DDD, ports, FastAPI)
- ✅ Modern tech stack (Python 3.12, Next.js 15)
- ✅ Excellent documentation
- ✅ Security design is good (contract-based RBAC)

**Negative:**
- ❌ Incomplete migrations (RBAC, CRUD, services)
- ❌ Security implementation gaps (deprecated permissions, audit logging)
- ❌ Performance risks (N+1, no circuit breaker)
- ❌ Code inconsistency (mixed styles, duplication)

**Root Cause:** Incremental development by different AI agents с different styles and priorities. Новые patterns introduced, но старый код не migrated.

**Recommendation:** Prioritize **REFACTOR-02** для RBAC migration (critical security), **REFACTOR-03** для performance fixes (N+1, indexes), и **DB REFACTOR** для schema consistency.

**СТАТУС АУДИТА:** ✅ COMPLETE

**NEXT STEPS:** Owner должен принять решение о приоритизации remediation tasks.

---

**Дата создания:** 2026-01-21  
**Версия:** 1.0  
**Аудитор:** GitHub Copilot Agent  
**Scope:** Full repository audit (backend, frontend, database, tests, docs)
