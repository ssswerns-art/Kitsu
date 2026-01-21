import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, validates

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
    )  # SECURITY: Only 'user', 'system', or 'anonymous' allowed
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

    # SECURITY: Database-level constraint to enforce allowed actor_type values
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system', 'anonymous')",
            name="valid_actor_type"
        ),
    )

    @validates("actor_type")
    def validate_actor_type(self, key: str, value: str) -> str:
        """
        SECURITY: Validate actor_type at ORM level to prevent spoofing.
        
        Per SECURITY-01 contract: only 'user', 'system', 'anonymous' are allowed.
        This prevents privilege escalation through actor_type manipulation.
        
        Args:
            key: The attribute name (always 'actor_type')
            value: The proposed actor_type value
            
        Returns:
            str: The validated actor_type
            
        Raises:
            ValueError: If actor_type is not in the allowed set
        """
        allowed = {"user", "system", "anonymous"}
        if value not in allowed:
            raise ValueError(
                f"Invalid actor_type '{value}'. "
                f"Must be one of: {', '.join(sorted(allowed))}"
            )
        return value
