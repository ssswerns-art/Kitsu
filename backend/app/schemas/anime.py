from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AnimeCreate(BaseModel):
    """Schema for creating a new anime (minimal required fields)"""
    title: str
    title_original: str | None = None
    description: str | None = None
    year: int | None = None
    status: str | None = None


class AnimeRead(BaseModel):
    """
    Full anime schema for details page.
    Contains all user-facing fields from the Anime model.
    """
    id: UUID

    # Titles
    title: str
    title_ru: str | None = None
    title_en: str | None = None
    title_original: str | None = None

    # Content
    description: str | None = None
    poster_url: str | None = None

    # Metadata
    year: int | None = None
    season: str | None = None  # winter, spring, summer, fall
    status: str | None = None  # ongoing, completed, announced, etc
    genres: list[str] | None = None

    # State management (draft, pending, published, broken, archived)
    state: str

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnimeListItem(BaseModel):
    """
    Compact anime schema for catalog/list views.
    Contains essential fields for displaying anime cards.
    """
    id: UUID

    # Titles
    title: str
    title_ru: str | None = None
    title_en: str | None = None

    # Visual
    poster_url: str | None = None

    # Metadata
    year: int | None = None
    season: str | None = None
    status: str | None = None
    genres: list[str] | None = None

    model_config = ConfigDict(from_attributes=True)
