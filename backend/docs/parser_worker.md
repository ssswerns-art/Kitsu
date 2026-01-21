# Parser Worker & Scheduler

## Overview

The parser worker and scheduler implement controlled auto-parsing functionality that only runs when explicitly enabled through the admin panel. The system follows strict safety principles to prevent spontaneous or runaway parsing.

## Key Principles

1. **Database as Single Source of Truth**: All configuration comes from `parser_settings` table
2. **Explicit Control**: Parser only runs when `parser_settings.mode = "auto"`
3. **No Side Effects in Manual Mode**: Worker sleeps when mode is "manual"
4. **Emergency Stop**: Mode can be switched to "manual" at any time
5. **Fail-Safe**: Critical errors automatically switch to manual mode
6. **System Actor**: Worker operates as `actor_type="system"`

## Components

### Worker (`app/parser/worker.py`)

The worker is an async infinite loop that:

1. Checks `parser_settings.mode` from database
2. If mode is "manual": sleeps and continues
3. If mode is "auto": queues scheduled tasks
4. Respects emergency stop signals
5. Logs all operations to `parser_job_logs`
6. Auto-switches to manual mode on critical errors

### Scheduler (`app/parser/scheduler.py`)

The scheduler determines when tasks should run:

1. **Catalog Sync**: Runs based on configurable interval (default: 24 hours)
2. **Episode Sync**: Runs when `enable_autoupdate=True` for ongoing anime
3. All intervals read from `parser_settings` table
4. No hardcoded scheduling values

## Usage

### Starting the Worker

```python
from app.parser.worker import run_worker

# Run in background task or separate process
await run_worker()
```

### Configuration

All configuration is managed through the admin panel or database:

```sql
-- Enable auto mode
UPDATE parser_settings 
SET mode = 'auto', enable_autoupdate = true 
WHERE id = 1;

-- Disable auto mode (emergency stop)
UPDATE parser_settings 
SET mode = 'manual' 
WHERE id = 1;
```

### Monitoring

Monitor worker activity through:

1. **Parser Jobs**: `SELECT * FROM parser_jobs ORDER BY started_at DESC`
2. **Job Logs**: `SELECT * FROM parser_job_logs ORDER BY created_at DESC`
3. **Audit Trail**: `SELECT * FROM audit_logs WHERE entity_type = 'parser_settings'`

## Safety Mechanisms

### Mode Checking

The worker checks `parser_settings.mode` before EVERY action:

```python
# Before queueing catalog sync
current_settings = await get_parser_settings(session)
if current_settings.mode != "auto":
    logger.warning("Mode changed to manual, aborting")
    return
```

### Emergency Mode Switch

On critical errors, the worker automatically switches to manual mode:

```python
async def _emergency_mode_switch(self, reason: str, details: str):
    # Switch mode to manual
    # Log to audit trail
    # Prevents runaway parsing
```

### Graceful Shutdown

The worker can be stopped gracefully:

```python
worker = ParserWorker()
await worker.shutdown()
```

## Testing

Run all parser tests:

```bash
cd backend
python -m pytest tests/test_parser_worker.py tests/test_parser_scheduler.py -v
```

### Test Coverage

1. ✅ Worker does NOT execute in manual mode
2. ✅ Worker starts executing only in auto mode
3. ✅ Mode changes respected during cycle
4. ✅ Emergency stop halts task queuing
5. ✅ Critical errors trigger mode switch
6. ✅ Scheduler respects intervals
7. ✅ Scheduler handles boundary conditions

## Deployment Considerations

### Production Setup

1. Run worker as background task in main app
2. Use process manager (e.g., systemd) for restart on crash
3. Monitor worker health through logs
4. Set up alerts for emergency mode switches

### Environment Variables

No environment variables needed. All configuration is in the database.

### Permissions

The worker requires:
- Database read/write access to parser tables
- No admin permissions (operates as system actor)

## Compliance

This implementation satisfies PARSER-04 requirements:

- ✅ Python 3.12 only
- ✅ No cron scripts or systemd timers
- ✅ Database as single source of truth
- ✅ Mode switching through admin panel
- ✅ Emergency stop integration
- ✅ Comprehensive logging
- ✅ Fail-safe on invariant violations
- ✅ System actor pattern
- ✅ Full test coverage

## API Integration

The worker integrates with existing admin endpoints:

- `POST /admin/parser/mode` - Toggle mode between manual/auto
- `POST /admin/parser/emergency-stop` - Emergency stop
- `GET /admin/parser/logs` - View worker logs
- `GET /admin/parser/dashboard` - Monitor worker status
