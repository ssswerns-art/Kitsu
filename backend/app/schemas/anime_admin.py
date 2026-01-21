"""
Admin schemas for anime management.

These schemas are used for the CMS-level anime management interface,
supporting filtering, sorting, and editing with full permission and audit controls.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# State machine valid transitions
VALID_STATE_TRANSITIONS = {
    "draft": ["pending", "broken", "archived"],
    "pending": ["published", "draft", "broken", "archived"],
    "published": ["archived", "broken"],
    "broken": ["draft", "pending", "archived"],
    "archived": ["draft"],
}


class AnimeAdminListFilter(BaseModel):
    """Filters for admin anime list."""
    
    state: Literal["draft", "pending", "published", "broken", "archived"] | None = None
    source: Literal["manual", "parser", "import"] | None = None
    has_video: bool | None = None
    has_errors: bool | None = None  # errors_count > 0
    
    # Pagination
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    
    # Sorting
    sort_by: Literal["updated_at", "created_at", "title"] = "updated_at"
    sort_order: Literal["asc", "desc"] = "desc"


class AnimeAdminListItem(BaseModel):
    """Anime item in admin list."""
    
    id: UUID
    title: str
    poster_url: str | None
    state: str
    source: str
    year: int | None
    status: str | None
    
    # Metadata for admin
    is_locked: bool
    locked_fields: list[str] | None
    has_video: bool  # Computed: has episodes with iframe_url
    errors_count: int  # Computed: count of errors/issues
    
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
    
    model_config = ConfigDict(from_attributes=True)


class AnimeAdminDetail(BaseModel):
    """Full anime details for admin editing."""
    
    id: UUID
    title: str
    title_ru: str | None
    title_en: str | None
    title_original: str | None
    description: str | None
    poster_url: str | None
    year: int | None
    season: str | None
    status: str | None
    genres: list[str] | None
    
    # State machine
    state: str
    
    # Ownership
    created_by: UUID | None
    updated_by: UUID | None
    source: str
    
    # Lock mechanism
    is_locked: bool
    locked_fields: list[str] | None
    locked_by: UUID | None
    locked_reason: str | None
    locked_at: datetime | None
    
    # Soft delete
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None
    delete_reason: str | None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    has_video: bool
    errors_count: int
    errors: list[str]  # List of error messages
    
    model_config = ConfigDict(from_attributes=True)


class AnimeAdminUpdate(BaseModel):
    """Schema for updating anime in admin."""
    
    # Editable fields
    title: str | None = None
    title_ru: str | None = None
    title_en: str | None = None
    title_original: str | None = None
    description: str | None = None
    poster_url: str | None = None
    year: int | None = None
    season: str | None = None
    status: str | None = None
    genres: list[str] | None = None
    
    # State transition
    state: Literal["draft", "pending", "published", "broken", "archived"] | None = None
    
    # Update reason (for audit)
    reason: str | None = None


class AnimeAdminUpdateResponse(BaseModel):
    """Response after updating anime."""
    
    success: bool
    anime: AnimeAdminDetail
    audit_log_id: UUID  # Reference to audit log entry
    warnings: list[str] = []  # e.g., "State changed to broken due to missing video"
    
    model_config = ConfigDict(from_attributes=True)


def validate_state_transition(current_state: str, new_state: str) -> bool:
    """
    Validate if state transition is allowed.
    
    Args:
        current_state: Current anime state
        new_state: Desired new state
        
    Returns:
        True if transition is valid, False otherwise
    """
    if current_state == new_state:
        return True
    
    allowed_states = VALID_STATE_TRANSITIONS.get(current_state, [])
    return new_state in allowed_states


def get_allowed_transitions(current_state: str) -> list[str]:
    """
    Get list of allowed state transitions from current state.
    
    Args:
        current_state: Current anime state
        
    Returns:
        List of allowed target states
    """
    return VALID_STATE_TRANSITIONS.get(current_state, [])
