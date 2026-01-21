import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class WatchProgress(Base):
    __tablename__ = "watch_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "anime_id"),
        # INVARIANT-2: Forward-only state - episode must be positive
        CheckConstraint("episode > 0", name="ck_watch_progress_episode_positive"),
        # INVARIANT-2: Forward-only state - progress must be in valid range
        CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="ck_watch_progress_percent_range",
        ),
        # INVARIANT-2: Forward-only state - position must be non-negative
        CheckConstraint(
            "position_seconds IS NULL OR position_seconds >= 0",
            name="ck_watch_progress_position_nonnegative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    anime_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("anime.id", ondelete="CASCADE"),  # INVARIANT-3: Referential integrity
        nullable=False,
        index=True,
    )
    episode: Mapped[int] = mapped_column(Integer, nullable=False)
    position_seconds: Mapped[int | None] = mapped_column(Integer)
    progress_percent: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_watched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
