# PARSER-03: Admin Parser Control Implementation

## Overview

This implementation provides RBAC-controlled admin panel for parser management, ensuring the parser **NEVER** starts automatically and can only be controlled by administrators.

## Key Features

### 1. RBAC Permissions

Three granular permissions have been added:

- `admin:parser.settings` - View and update parser settings
- `admin:parser.emergency` - Emergency stop capability  
- `admin:parser.logs` - View parser logs

These replace the overly broad `admin:*` permission for parser endpoints.

### 2. Backend Endpoints

#### Settings Management
- `GET /admin/parser/settings` - Get current settings (requires `admin:parser.settings`)
- `POST /admin/parser/settings` - Update settings with audit logging (requires `admin:parser.settings`)

#### Mode Control
- `POST /admin/parser/mode` - Toggle between manual/auto mode (requires `admin:parser.settings`)
  - Logs mode changes to audit_logs
  - Supports optional reason parameter

#### Emergency Stop
- `POST /admin/parser/emergency-stop` - Immediately stop parser (requires `admin:parser.emergency`)
  - Sets mode to "manual"
  - Stops all running jobs
  - Logs with WARNING level to audit_logs

#### Logs
- `GET /admin/parser/logs` - Query parser logs (requires `admin:parser.logs`)
  - Filters: level, source, from_date, to_date
  - Returns up to 500 logs

### 3. Frontend Pages

#### Parser Dashboard (`/admin/parser`)
- Mode indicator (Auto/Manual with color coding)
- Dry-run status
- Enabled sources
- Statistics (anime count, unmapped, episodes, jobs, errors)
- Action buttons:
  - Enable/Disable Auto Mode
  - Emergency Stop

#### Parser Settings (`/admin/parser/settings`)
- Mode display (read-only, changed via dashboard)
- Dry-run toggle
- Auto-update configuration
- Translation type filters
- Translation and quality priorities
- Blacklists (titles and external IDs)
- Confirmation dialogs for dangerous actions

#### Parser Logs (`/admin/parser/logs`)
- Read-only log viewer
- Filters: level (ERROR/WARNING/INFO), source, date range
- Paginated results

### 4. Audit Logging

All critical operations are logged:

- **Mode changes**: 
  ```json
  {
    "action": "parser.mode_change",
    "entity_type": "parser_settings",
    "before": {"mode": "manual"},
    "after": {"mode": "auto"},
    "reason": "User provided reason"
  }
  ```

- **Settings updates**:
  ```json
  {
    "action": "parser_settings.update",
    "entity_type": "parser_settings",
    "before": {...},
    "after": {...}
  }
  ```

- **Emergency stop**:
  ```json
  {
    "action": "parser.emergency_stop",
    "entity_type": "parser_settings",
    "before": {"mode": "auto", "status": "running"},
    "after": {"mode": "manual", "status": "stopped"},
    "reason": "Emergency reason"
  }
  ```

## Security Guarantees

1. **No Auto-start**: Parser mode defaults to "manual" in database (server_default)
2. **Permission Checks**: All endpoints require specific permissions
3. **Audit Trail**: All changes are logged with actor, IP, and user agent
4. **parser_bot Access**: No access to settings endpoints (lacks required permissions)

## Database Schema

The `parser_settings` table already includes:
- `mode` (String) - default: "manual"
- `dry_run` (Boolean) - default: false
- `enable_autoupdate` (Boolean) - default: false
- `allowed_translation_types` (JSON)
- `allowed_translations` (JSON)
- `allowed_qualities` (JSON)
- `preferred_translation_priority` (JSON)
- `preferred_quality_priority` (JSON)
- `blacklist_titles` (JSON)
- `blacklist_external_ids` (JSON)
- `updated_at` (DateTime with timezone)

## Testing

Comprehensive test suite includes:

- Permission enforcement tests
- Mode toggle tests (manual ↔ auto)
- Emergency stop tests
- Settings update with audit logging
- Log filtering tests
- RBAC permission tests

All tests pass: **12 passed, 1 warning**

## Compliance

- ✅ Parser NEVER starts automatically
- ✅ Auto-parsing enabled ONLY by administrator
- ✅ All settings changes logged to audit_logs
- ✅ Default mode = "manual"
- ✅ parser_bot lacks access to settings
- ✅ No env-variable based enable/disable
- ✅ No cron/auto-scheduler
- ✅ Python 3.12 only
- ✅ PARSER-01 and PARSER-02 invariants respected

## Usage Example

### Enable Auto Mode

```bash
POST /api/admin/parser/mode
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "mode": "auto",
  "reason": "Enabling scheduled parsing for production"
}
```

### Emergency Stop

```bash
POST /api/admin/parser/emergency-stop
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "reason": "High error rate detected, stopping parser"
}
```

### Update Settings

```bash
POST /api/admin/parser/settings
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "dry_run_default": true,
  "allowed_qualities": ["1080p", "720p"],
  "allowed_translation_types": ["voice", "sub"]
}
```

## Migration Notes

No database migration required - existing schema is compliant.

## Future Work (Not in Scope)

- PARSER-04: Auto-worker implementation (when/if needed)
- Parser scheduling UI (depends on PARSER-04)
- Advanced filtering in logs page
