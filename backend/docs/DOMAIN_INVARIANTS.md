# TASK-4B: Domain Invariants Implementation

## Overview

This document describes the domain invariants enforced to prevent data drift and ensure consistent state across the system.

## Core Principle

**Domain + Database = Source of Truth**  
All invariants are enforced in the domain/application layer and backed by database constraints.

## Invariants

### INVARIANT-1: Single Source of Truth

**Definition**: Each domain fact has ONE canonical representation. No duplicate fields with the same meaning.

**Implementation**:
- ✅ `WatchProgress` has single progress representation (episode + position_seconds OR progress_percent)
- ✅ `Favorite` has single representation (user_id, anime_id)
- ✅ No redundant state fields

**Verification**: Code review of domain models

---

### INVARIANT-2: Forward-only State

**Definition**: Certain state transitions cannot go backwards to prevent accidental data loss.

**Rules**:

#### Episode Number (WatchProgress)
```python
# ALLOWED:
episode: 1 → 2  # Progress to next episode
episode: 2 → 2  # Rewatch same episode

# FORBIDDEN:
episode: 5 → 3  # Cannot go back (raises InvariantViolation)
```

**Implementation**:
- Domain: `validate_forward_only_episode()` in `domain/invariants.py`
- Database: `CHECK (episode > 0)` constraint
- Use-case: Checked in `_apply_watch_progress()` before update

#### Progress Percentage (WatchProgress)
```python
# Within SAME episode:
# ALLOWED:
progress: 20% → 50%  # Progress increases
progress: 50% → 50%  # Same progress (idempotent)

# FORBIDDEN:
progress: 80% → 40%  # Cannot decrease within same episode

# When changing episodes:
episode: 1, progress: 80% → episode: 2, progress: 10%  # ALLOWED (new episode resets)
```

**Implementation**:
- Domain: `validate_forward_only_progress()` in `domain/invariants.py`
- Database: `CHECK (progress_percent >= 0 AND progress_percent <= 100)` constraint
- Use-case: Checked in `_apply_watch_progress()` before update

#### Position Seconds (WatchProgress)
```python
# ALLOWED:
position: 0      # Start
position: 120    # Any positive value

# FORBIDDEN:
position: -10    # Negative position (raises InvariantViolation)
```

**Implementation**:
- Domain: `validate_position_bounds()` in `domain/invariants.py`
- Database: `CHECK (position_seconds IS NULL OR position_seconds >= 0)` constraint

---

### INVARIANT-3: Referential Consistency

**Definition**: No orphaned entities. All relationships must be valid.

**Rules**:

#### Favorite → Anime
```python
# FORBIDDEN:
add_favorite(user_id=U1, anime_id=NONEXISTENT)  # Raises InvariantViolation
```

**Implementation**:
- Domain: `validate_referential_integrity_anime()` in `domain/invariants.py`
- Database: `FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE`
- Use-case: Checked in `_apply_add_favorite()` before insert

#### WatchProgress → Anime
```python
# FORBIDDEN:
update_progress(user_id=U1, anime_id=NONEXISTENT, ...)  # Raises InvariantViolation
```

**Implementation**:
- Domain: `validate_referential_integrity_anime()` in `domain/invariants.py`
- Database: `FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE`
- Use-case: Checked in `_apply_watch_progress()` before insert/update

#### Episode → Release → Anime
```python
# FORBIDDEN:
create_episode(release_id=NONEXISTENT, ...)  # Fails at DB level
```

**Implementation**:
- Database: `FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE`
- Database: `FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE` (in Release)

---

### INVARIANT-4: Domain > API > Background

**Definition**: Neither API nor background jobs can bypass domain rules. ALL checks happen in domain/application layer.

**Implementation**:
- ✅ All validation in `domain/invariants.py`
- ✅ Use-cases (`use_cases/*`) enforce invariants before DB operations
- ✅ Background jobs use same use-cases as API
- ✅ NO special paths that skip validation

**Verification**:
- API endpoints call use-cases
- Background job handlers call use-cases
- No direct database access bypassing use-cases

---

### INVARIANT-5: Explicit Rejection

**Definition**: When operation violates invariant, it either deterministically skips OR raises explicit domain error. Never silent failure.

**Behaviors**:

#### Deterministic Skip (idempotent)
```python
# Operation already applied → skip
add_favorite(user_id, anime_id)  # Creates favorite
add_favorite(user_id, anime_id)  # Logs: idempotent_skip, no error

# Exact state already exists → skip
update_progress(user_id, anime_id, episode=5, position=120)  # Updates
update_progress(user_id, anime_id, episode=5, position=120)  # Logs: idempotent_skip
```

#### Explicit Domain Error
```python
# Invariant violation → InvariantViolation exception
update_progress(user_id, anime_id, episode=3)  # Currently on episode 5
# Raises: InvariantViolation("Cannot decrease episode number from 5 to 3")
# Logs: invariant_violation invariant=INVARIANT-2.episode_forward_only
```

**Implementation**:
- Idempotent skip: Logged as `idempotent_skip` in use-cases
- Invariant violation: `InvariantViolation` exception from `domain/invariants.py`
- All violations logged: `invariant_violation` with details

---

## Implementation Details

### Module Structure

```
app/
├── domain/
│   ├── invariants.py          # Domain invariant validation functions
│   └── ports/                 # Repository interfaces
├── use_cases/
│   ├── watch/
│   │   └── update_progress.py # Enforces invariants before persistence
│   └── favorites/
│       ├── add_favorite.py    # Enforces invariants before persistence
│       └── remove_favorite.py
└── models/
    ├── watch_progress.py      # DB CHECK constraints
    ├── favorite.py            # DB FOREIGN KEY constraints
    └── episode.py             # DB FOREIGN KEY constraints
```

### Exception Hierarchy

```python
Exception
└── InvariantViolation (domain error)
    ├── invariant: str (e.g., "INVARIANT-2.episode_forward_only")
    ├── details: dict (context for debugging)
    └── Automatically logs invariant_violation
```

### Logging Format

**Invariant Skip** (operation succeeds but is no-op):
```
idempotent_skip operation=watch-progress user_id=... anime_id=... episode=5 reason=exact_match_exists
```

**Invariant Violation** (operation fails with error):
```
invariant_violation invariant=INVARIANT-2.episode_forward_only message=Cannot decrease episode number from 5 to 3 details={'user_id': '...', 'anime_id': '...', 'current_episode': 5, 'new_episode': 3}
```

---

## Testing Invariants

### Test Scenario 1: Forward-only episode

```python
# Setup: User has progress on episode 5
await update_progress(user_id, anime_id, episode=5, position=120)

# Test: Try to go back to episode 3
with pytest.raises(InvariantViolation) as exc:
    await update_progress(user_id, anime_id, episode=3, position=60)

assert exc.value.invariant == "INVARIANT-2.episode_forward_only"
assert exc.value.details["current_episode"] == 5
assert exc.value.details["new_episode"] == 3
```

### Test Scenario 2: Forward-only progress

```python
# Setup: User at 80% on episode 5
await update_progress(user_id, anime_id, episode=5, progress_percent=80.0)

# Test: Try to decrease progress on same episode
with pytest.raises(InvariantViolation) as exc:
    await update_progress(user_id, anime_id, episode=5, progress_percent=40.0)

assert exc.value.invariant == "INVARIANT-2.progress_forward_only"
```

### Test Scenario 3: Referential integrity

```python
# Test: Try to add favorite for non-existent anime
non_existent_anime_id = uuid.uuid4()

with pytest.raises(InvariantViolation) as exc:
    await add_favorite(user_id, non_existent_anime_id)

assert exc.value.invariant == "INVARIANT-3.anime_referential_integrity"
assert exc.value.details["operation"] == "add favorite"
```

### Test Scenario 4: Idempotent operations

```python
# First call: Creates favorite
result1 = await add_favorite(user_id, anime_id)

# Second call: Idempotent skip (no error)
result2 = await add_favorite(user_id, anime_id)

# Both return successfully (result1 and result2 may be the same or different objects)
# Logs show: idempotent_skip operation=favorite:add reason=already_exists
```

---

## Database Constraints

### WatchProgress

```sql
-- INVARIANT-2: Episode must be positive
ALTER TABLE watch_progress 
ADD CONSTRAINT ck_watch_progress_episode_positive 
CHECK (episode > 0);

-- INVARIANT-2: Progress must be in valid range
ALTER TABLE watch_progress 
ADD CONSTRAINT ck_watch_progress_percent_range 
CHECK (progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100));

-- INVARIANT-2: Position must be non-negative
ALTER TABLE watch_progress 
ADD CONSTRAINT ck_watch_progress_position_nonnegative 
CHECK (position_seconds IS NULL OR position_seconds >= 0);

-- INVARIANT-3: Referential integrity
ALTER TABLE watch_progress 
ADD CONSTRAINT fk_watch_progress_anime 
FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE;
```

### Favorites

```sql
-- INVARIANT-3: Referential integrity
ALTER TABLE favorites 
ADD CONSTRAINT fk_favorites_anime 
FOREIGN KEY (anime_id) REFERENCES anime(id) ON DELETE CASCADE;
```

### Episodes

```sql
-- INVARIANT-3: Referential integrity
ALTER TABLE episodes 
ADD CONSTRAINT fk_episodes_release 
FOREIGN KEY (release_id) REFERENCES releases(id) ON DELETE CASCADE;
```

---

## Migration Path

### Step 1: Add domain validation (✅ Complete)
- Created `domain/invariants.py`
- Added validation functions for all invariants
- Added `InvariantViolation` exception

### Step 2: Update use-cases (✅ Complete)
- `update_progress`: Enforces forward-only state
- `add_favorite`: Enforces referential integrity
- All operations log violations

### Step 3: Add DB constraints (✅ Complete)
- Added CHECK constraints to `WatchProgress` model
- Existing FOREIGN KEY constraints documented

### Step 4: Create migration (⏳ Next)
- Generate Alembic migration for new CHECK constraints
- Apply to existing databases

---

## Benefits

1. **Data Quality**: Prevents invalid state transitions
2. **Debugging**: Clear error messages with context
3. **Observability**: All violations logged
4. **Safety**: Database constraints as last line of defense
5. **Scalability**: Invariants hold across multiple workers
6. **Maintainability**: Centralized validation logic

---

## Future Work

1. Add more specific invariants as domain evolves
2. Add performance metrics for invariant checks
3. Add alerts for high invariant violation rates
4. Extend to parser entities (already have atomic operations)
