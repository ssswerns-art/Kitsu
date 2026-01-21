# TASK-4A: EXACTLY-ONCE EFFECT Implementation

## Overview

This document describes the implementation of exactly-once semantics (idempotency) for all critical operations in the Kitsu system.

## Principle

**Source of Truth**: Domain + Database (NOT runner, scheduler, or Redis)  
**Guarantee**: Operation can execute N times, but effect occurs ≤ 1 time

## Implementation Summary

### 1. Watch Progress (`user_id`, `anime_id`)

**File**: `app/use_cases/watch/update_progress.py`

**Idempotency Key**: `(user_id, anime_id)`

**Mechanism**:
- Check if exact update already applied before modifying
- Compare episode, position_seconds, and progress_percent
- Log `idempotent_skip` when effect already applied
- Database: UNIQUE constraint on `(user_id, anime_id)`

**Behavior**:
```python
# First execution: Creates or updates progress
# Retry with same data: idempotent_skip logged, no DB change
# Retry with different data: Update applied (intentional)
```

### 2. Add Favorite (`user_id`, `anime_id`)

**File**: `app/use_cases/favorites/add_favorite.py`

**Idempotency Key**: `(user_id, anime_id)`

**Mechanism**:
- Check if favorite exists before insertion
- Log `idempotent_skip` if already exists
- Commit transaction cleanly in both cases
- Database: UNIQUE constraint on `(user_id, anime_id)`

**Behavior**:
```python
# First execution: Creates favorite
# Retry: idempotent_skip logged, no duplicate created
```

### 3. Remove Favorite (`user_id`, `anime_id`)

**File**: `app/use_cases/favorites/remove_favorite.py`

**Idempotency Key**: `(user_id, anime_id)`

**Mechanism**:
- Check if favorite exists before deletion
- Log `idempotent_skip` if not found
- Handle concurrent deletions gracefully
- Database: Deletion is naturally idempotent

**Behavior**:
```python
# First execution: Deletes favorite
# Retry: idempotent_skip logged (not found)
# Concurrent deletion: idempotent_skip logged (concurrent removal)
```

### 4. Parser Operations

**Files**:
- `app/parser/repositories/anime_external_repo.py`
- `app/parser/repositories/episode_external_repo.py`
- `app/parser/repositories/schedule_repo.py`

**Idempotency Keys**:
- Anime: `(source_id, external_id)`
- Episodes: `(anime_id, source_id, episode_number)`
- Schedule: `(anime_id, source_id, episode_number)`
- Translations: `(anime_id, source_id, translation_code)`

**Mechanism**:
- ATOMIC operations via `INSERT ... ON CONFLICT DO UPDATE`
- Database handles idempotency via unique constraints
- Log all upsert operations for observability
- No read-then-write gap (single atomic operation)

**Behavior**:
```python
# First execution: INSERT or UPDATE based on conflict
# Retry: UPDATE with same or new data (deterministic)
# Database ensures exactly-once constraint enforcement
```

## Invariants Satisfied

### INVARIANT-1: Exactly-once effect
✅ **Satisfied**: Each operation either applies effect OR deterministically skips

### INVARIANT-2: Idempotency in domain/application
✅ **Satisfied**: All checks in use-cases and repositories, NOT in runner/scheduler/Redis

### INVARIANT-3: Deterministic state
✅ **Satisfied**: Retry produces same outcome with explicit logging

### INVARIANT-4: No global locks
✅ **Satisfied**: Uses domain-specific unique constraints, no mutex or global state

## Testing Idempotency

### Manual Test Scenarios

**Scenario 1**: Repeated watch progress update
```python
# Execute twice with same parameters
update_progress(user_id=U1, anime_id=A1, episode=5, position=120)
update_progress(user_id=U1, anime_id=A1, episode=5, position=120)

# Expected: 
# - First call: Creates/updates progress
# - Second call: Logs "idempotent_skip", no DB change
```

**Scenario 2**: Concurrent favorite additions
```python
# Two workers try to add same favorite simultaneously
add_favorite(user_id=U1, anime_id=A1)  # Worker 1
add_favorite(user_id=U1, anime_id=A1)  # Worker 2

# Expected:
# - One succeeds (creates favorite)
# - Other logs "idempotent_skip" (already exists)
# - Result: Exactly 1 favorite in DB
```

**Scenario 3**: Parser retry
```python
# Parser job fails mid-execution and retries
sync_episodes(source_id=1, episodes=[E1, E2, E3])
# Crash after E1, E2 persisted
sync_episodes(source_id=1, episodes=[E1, E2, E3])

# Expected:
# - E1, E2: UPSERT (conflict → update)
# - E3: UPSERT (no conflict → insert)
# - Result: All 3 episodes in DB, no duplicates
```

## Log Format

All operations log in structured format:

**Idempotent Skip**:
```
idempotent_skip operation=<name> <domain_key> reason=<reason>
```

**Effect Applied**:
```
operation=<name> action=<create|update|delete> <domain_key>
```

Examples:
```
idempotent_skip operation=watch-progress user_id=... anime_id=... episode=5 reason=exact_match_exists
operation=favorite:add action=create user_id=... anime_id=... favorite_id=...
idempotent_skip operation=favorite:remove user_id=... anime_id=... reason=not_found
operation=parser:episodes action=upsert source_id=1 count=42
```

## Migration Notes

### No Breaking Changes

- ✅ No changes to API contracts
- ✅ No changes to database schema (constraints already exist)
- ✅ No changes to background job infrastructure
- ✅ Backward compatible with existing code

### What Changed

1. **Added explicit idempotency checks** in domain layer
2. **Added structured logging** for observability
3. **Documented idempotency keys** in code comments
4. **Verified atomic operations** use correct constraints

### What Didn't Change

- ❌ Runner
- ❌ Scheduler
- ❌ Redis
- ❌ Database schema
- ❌ API endpoints
- ❌ Background job system

## Benefits

1. **Safe Retries**: Jobs can be retried without side effects
2. **Scalable Workers**: Multiple workers can process same job safely
3. **Crash Recovery**: System recovers gracefully from crashes
4. **Deterministic Behavior**: Same input → same output, always
5. **Observable**: Explicit logging of all idempotency decisions

## Future Work

This implementation provides exactly-once semantics for all critical operations. Future enhancements could include:

1. Metrics collection for `idempotent_skip` events
2. Alert on unexpected idempotency patterns
3. Performance optimization for high-frequency operations
4. Extended testing suite for idempotency edge cases
