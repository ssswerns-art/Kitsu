from typing import Literal

from pydantic import BaseModel, ConfigDict


class ParserSourceRead(BaseModel):
    id: int
    code: str
    enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ParserSettingsRead(BaseModel):
    mode: Literal["manual", "auto"]
    stage_only: bool
    autopublish_enabled: bool
    enable_autoupdate: bool
    update_interval_minutes: int
    dry_run_default: bool
    allowed_translation_types: list[Literal["voice", "sub"]]
    allowed_translations: list[str]
    allowed_qualities: list[str]
    preferred_translation_priority: list[str]
    preferred_quality_priority: list[str]
    blacklist_titles: list[str]
    blacklist_external_ids: list[str]

    model_config = ConfigDict(from_attributes=True)


class ParserSettingsUpdate(BaseModel):
    mode: Literal["manual", "auto"] | None = None
    stage_only: bool | None = None
    autopublish_enabled: bool | None = None
    enable_autoupdate: bool | None = None
    update_interval_minutes: int | None = None
    dry_run_default: bool | None = None
    allowed_translation_types: list[Literal["voice", "sub"]] | None = None
    allowed_translations: list[str] | None = None
    allowed_qualities: list[str] | None = None
    preferred_translation_priority: list[str] | None = None
    preferred_quality_priority: list[str] | None = None
    blacklist_titles: list[str] | None = None
    blacklist_external_ids: list[str] | None = None


class ParserMatchRequest(BaseModel):
    anime_external_id: int
    anime_id: str


class ParserUnmatchRequest(BaseModel):
    anime_external_id: int


class ParserRunRequest(BaseModel):
    sources: list[Literal["shikimori", "kodik"]]
    mode: Literal["dry_run", "persist"]


class AnimeExternalRead(BaseModel):
    id: int
    anime_id: str | None
    source: str
    external_id: str
    title_raw: str | None
    year: int | None
    status: str | None
    matched_by: str | None

    model_config = ConfigDict(from_attributes=True)


class ParserDashboardRead(BaseModel):
    sources: list[ParserSourceRead]
    anime_external_count: int
    unmapped_anime_count: int
    episodes_external_count: int
    jobs_last_24h: int
    errors_count: int


class ParserPublishAnimeRead(BaseModel):
    anime_id: str
    created: bool


class ParserPublishEpisodeRequest(BaseModel):
    anime_id: str
    episode_number: int


class ParserPublishEpisodeRead(BaseModel):
    episode_id: str
    created: bool


class ParserPublishAnimePayload(BaseModel):
    title: str
    title_ru: str | None = None
    title_en: str | None = None
    title_original: str | None = None
    description: str | None = None
    poster_url: str | None = None
    year: int | None = None
    season: str | None = None
    status: str | None = None
    genres: list[str] | None = None


class ParserPublishPreviewRead(BaseModel):
    anime_external_id: int
    anime_id: str | None
    external: ParserPublishAnimePayload
    current: ParserPublishAnimePayload | None
    changes: list[str]


class ParserModeToggleRequest(BaseModel):
    mode: Literal["manual", "auto"]
    reason: str | None = None


class ParserEmergencyStopRequest(BaseModel):
    reason: str


class ParserJobLogRead(BaseModel):
    id: int
    job_id: int
    level: str
    message: str
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ParserLogFilter(BaseModel):
    level: Literal["error", "warning", "info"] | None = None
    source: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    limit: int = 100
