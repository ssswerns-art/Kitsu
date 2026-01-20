import uuid
from datetime import datetime
from typing import Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        actor_id: uuid.UUID | None,
        actor_type: str,
        action: str,
        entity_type: str,
        entity_id: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            reason=reason,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(audit_log)
        await self.session.commit()
        await self.session.refresh(audit_log)
        return audit_log

    async def get_by_id(self, audit_log_id: uuid.UUID) -> AuditLog | None:
        return await self.session.get(AuditLog, audit_log_id)

    async def list_by_entity(self, entity_type: str, entity_id: str, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_actor(self, actor_id: uuid.UUID, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_action(self, action: str, limit: int = 100) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_filters(
        self,
        actor_id: uuid.UUID | None = None,
        actor_type: str | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLog]:
        query = select(AuditLog)
        
        conditions = []
        if actor_id is not None:
            conditions.append(AuditLog.actor_id == actor_id)
        if actor_type is not None:
            conditions.append(AuditLog.actor_type == actor_type)
        if action is not None:
            conditions.append(AuditLog.action == action)
        if entity_type is not None:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        if from_date is not None:
            conditions.append(AuditLog.created_at >= from_date)
        if to_date is not None:
            conditions.append(AuditLog.created_at <= to_date)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
