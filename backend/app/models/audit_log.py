import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # 'user' or 'system'
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g., 'anime.edit', 'episode.delete'
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g., 'anime', 'episode'
    entity_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )  # UUID as string
    before: Mapped[dict | None] = mapped_column(JSON)  # state before change
    after: Mapped[dict | None] = mapped_column(JSON)  # state after change
    reason: Mapped[str | None] = mapped_column(Text)  # optional reason for change
    ip_address: Mapped[str | None] = mapped_column(String(45))  # IPv4/IPv6
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
