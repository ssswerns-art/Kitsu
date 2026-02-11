from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EpisodeRead(BaseModel):
    """
    Full episode schema with all details.
    Used for single episode retrieval.
    """
    id: UUID
    release_id: UUID
    number: int
    title: str | None = None

    # Video sources and options
    iframe_url: str | None = None
    available_translations: list[str] | None = None
    available_qualities: list[str] | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EpisodeListItem(BaseModel):
    """
    Episode schema for list views.
    Contains all necessary fields for episode selection and playback.
    """
    id: UUID
    number: int
    title: str | None = None

    # Video sources and options - CRITICAL for frontend
    iframe_url: str | None = None
    available_translations: list[str] | None = None
    available_qualities: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)
