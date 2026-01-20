import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from ...crud.audit_log import AuditLogRepository
from ...models.user import User


class AuditService:
    """Service for logging audit events."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: str | uuid.UUID,
        actor: User | None = None,
        actor_type: str = "user",
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an audit event."""
        actor_id = actor.id if actor else None
        entity_id_str = str(entity_id)
        
        await self.audit_repo.create(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id_str,
            before=before,
            after=after,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_create(
        self,
        entity_type: str,
        entity_id: str | uuid.UUID,
        entity_data: dict[str, Any],
        actor: User | None = None,
        actor_type: str = "user",
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a create event."""
        await self.log(
            action=f"{entity_type}.create",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            actor_type=actor_type,
            before=None,
            after=entity_data,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_update(
        self,
        entity_type: str,
        entity_id: str | uuid.UUID,
        before_data: dict[str, Any],
        after_data: dict[str, Any],
        actor: User | None = None,
        actor_type: str = "user",
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an update event."""
        await self.log(
            action=f"{entity_type}.update",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            actor_type=actor_type,
            before=before_data,
            after=after_data,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_delete(
        self,
        entity_type: str,
        entity_id: str | uuid.UUID,
        entity_data: dict[str, Any],
        actor: User | None = None,
        actor_type: str = "user",
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a delete event."""
        await self.log(
            action=f"{entity_type}.delete",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            actor_type=actor_type,
            before=entity_data,
            after=None,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_lock(
        self,
        entity_type: str,
        entity_id: str | uuid.UUID,
        locked_fields: list[str],
        actor: User | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log a lock event."""
        await self.log(
            action=f"{entity_type}.lock",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            actor_type="user",
            after={"locked_fields": locked_fields},
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_unlock(
        self,
        entity_type: str,
        entity_id: str | uuid.UUID,
        actor: User | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an unlock event."""
        await self.log(
            action=f"{entity_type}.unlock",
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            actor_type="user",
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
