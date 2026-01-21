import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from ...crud.audit_log import AuditLogRepository
from ...models.user import User


class AuditService:
    """Service for logging audit events with security enforcement.
    
    SECURITY: All audit logs enforce actor_type validation per SECURITY-01 contract.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditLogRepository(session)

    def _validate_actor_type(self, actor_type: str) -> None:
        """
        SECURITY: Validate actor_type to prevent spoofing.
        
        Per SECURITY-01 contract, only 'user', 'system', 'anonymous' are allowed.
        
        Args:
            actor_type: The actor type to validate
            
        Raises:
            ValueError: If actor_type is invalid
        """
        allowed = {"user", "system", "anonymous"}
        if actor_type not in allowed:
            raise ValueError(
                f"Invalid actor_type '{actor_type}'. "
                f"Must be one of: {', '.join(sorted(allowed))}"
            )

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
    ):
        """Log an audit event.
        
        SECURITY: Validates actor_type before logging to prevent privilege escalation.
        
        Args:
            action: The action performed (e.g., 'anime.edit')
            entity_type: The type of entity (e.g., 'anime')
            entity_id: The ID of the entity
            actor: The user performing the action (None for system/anonymous)
            actor_type: Type of actor - 'user', 'system', or 'anonymous'
            before: State before the change
            after: State after the change
            reason: Optional reason for the change
            ip_address: IP address of the request
            user_agent: User agent of the request
            
        Raises:
            ValueError: If actor_type is invalid
        """
        # SECURITY: Validate actor_type before creating audit log
        self._validate_actor_type(actor_type)
        
        actor_id = actor.id if actor else None
        entity_id_str = str(entity_id)
        
        return await self.audit_repo.create(
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
    ):
        """Log an update event."""
        return await self.log(
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
    
    async def log_permission_denied(
        self,
        permission: str,
        actor: User | None = None,
        actor_type: str = "user",
        resource: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Log a permission denied (403) event.
        
        SECURITY: Required per SECURITY-01 to audit all permission denials.
        
        Args:
            permission: The permission that was denied
            actor: The user who was denied
            actor_type: Type of actor
            resource: Optional resource that was being accessed
            ip_address: IP address of the request
            user_agent: User agent of the request
        """
        await self.log(
            action="security.permission_denied",
            entity_type="permission",
            entity_id=permission,
            actor=actor,
            actor_type=actor_type,
            after={
                "permission": permission,
                "resource": resource,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    async def log_privilege_escalation_attempt(
        self,
        actor: User | None = None,
        actor_type: str = "user",
        attempted_role: str | None = None,
        attempted_permission: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Log a privilege escalation attempt.
        
        SECURITY: Required per SECURITY-01 to audit escalation attempts.
        
        Args:
            actor: The user who attempted escalation
            actor_type: Type of actor
            attempted_role: Role they tried to assume
            attempted_permission: Permission they tried to use
            ip_address: IP address of the request
            user_agent: User agent of the request
        """
        await self.log(
            action="security.escalation_attempt",
            entity_type="security",
            entity_id="privilege_escalation",
            actor=actor,
            actor_type=actor_type,
            after={
                "attempted_role": attempted_role,
                "attempted_permission": attempted_permission,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
