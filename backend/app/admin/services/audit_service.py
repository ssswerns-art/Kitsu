"""
Audit Service - Centralized audit logging for admin write actions.

PHASE 8: Implements fire-and-forget async audit logging.
All audit logs are written to standard logger as JSON for now.
Future phases may persist to database.

CRITICAL: Audit failures must NEVER block admin operations.
All audit calls wrapped in try/except for safety.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class AuditService:
    """
    Service for logging admin actions in a structured, auditable format.
    
    All logging is fire-and-forget - failures do not propagate to caller.
    """

    async def log_admin_action(
        self,
        *,
        actor_id: UUID,
        action: str,
        target_type: str,
        target_id: str | UUID,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """
        Log an admin action in structured JSON format.
        
        This method is fire-and-forget - it will never raise exceptions
        to the caller, ensuring audit failures don't block operations.
        
        Args:
            actor_id: UUID of the user performing the action
            action: Action identifier (e.g., "admin.users.roles.update")
            target_type: Type of target entity (e.g., "user", "role")
            target_id: ID of the target entity
            payload: Optional dict with action details
        """
        try:
            # Convert target_id to string for consistent JSON serialization
            target_id_str = str(target_id)
            
            # Build structured audit log entry
            audit_entry = {
                "actor_id": str(actor_id),
                "action": action,
                "target_type": target_type,
                "target_id": target_id_str,
                "payload": payload or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            # Log as JSON to standard logger
            # Future phases may persist to database
            logger.info(
                "AUDIT: %s",
                json.dumps(audit_entry, ensure_ascii=False),
                extra={"audit_entry": audit_entry},
            )
            
        except Exception as e:
            # CRITICAL: Never let audit failures block the actual operation
            # Log the audit failure itself, but don't propagate
            logger.error(
                "Audit logging failed for action %s: %s",
                action,
                str(e),
                exc_info=True,
            )
