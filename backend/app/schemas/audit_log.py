import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class AuditLogCreate(BaseModel):
    actor_id: uuid.UUID | None
    actor_type: str = Field(..., min_length=1, max_length=50)  # 'user' or 'system'
    action: str = Field(..., min_length=1, max_length=100)
    entity_type: str = Field(..., min_length=1, max_length=100)
    entity_id: str = Field(..., min_length=1, max_length=255)
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditLogResponse(AuditLogCreate):
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogFilter(BaseModel):
    actor_id: uuid.UUID | None = None
    actor_type: str | None = None
    action: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
