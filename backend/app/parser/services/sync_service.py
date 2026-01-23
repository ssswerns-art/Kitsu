from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import ParserSettings
from ..domain.entities import AnimeExternal, EpisodeExternal, ScheduleItem, TranslationExternal
from ..ports.catalog_source import CatalogSourcePort
from ..ports.episode_source import EpisodeSourcePort
from ..ports.schedule_source import ScheduleSourcePort
from ..repositories.anime_external_repo import AnimeExternalRepository
from ..repositories.episode_external_repo import EpisodeExternalRepository
from ..repositories.schedule_repo import ScheduleRepository
from ..tables import (
    parser_job_logs,
    parser_jobs,
    parser_settings,
    parser_sources,
)


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


async def _commit(session: AsyncSession) -> None:
    # Removed: Caller is responsible for transaction management
    # This was previously used to commit, but now transactions should be
    # managed at the service boundary (router or worker level)
    pass


def _normalize_setting_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value is None:
        return []
    return [str(value)]


def _settings_to_row(settings: ParserSettings) -> dict[str, Any]:
    return {
        "mode": settings.mode,
        "stage_only": True,
        "publish_enabled": False,
        "enable_autoupdate": settings.enable_autoupdate,
        "update_interval_minutes": settings.update_interval_minutes,
        "dry_run": settings.dry_run_default,
        "allowed_translation_types": list(settings.allowed_translation_types),
        "allowed_translations": list(settings.allowed_translations),
        "allowed_qualities": list(settings.allowed_qualities),
        "preferred_translation_priority": list(settings.preferred_translation_priority),
        "preferred_quality_priority": list(settings.preferred_quality_priority),
        "blacklist_titles": list(settings.blacklist_titles),
        "blacklist_external_ids": list(settings.blacklist_external_ids),
    }


def _settings_from_row(row: Mapping[str, Any] | None) -> ParserSettings:
    defaults = ParserSettings()
    if row is None:
        return defaults
    allowed_types = [
        item
        for item in (value.lower() for value in _normalize_setting_list(row.get("allowed_translation_types")))
        if item in {"voice", "sub"}
    ]
    return ParserSettings(
        mode=row.get("mode") or defaults.mode,
        stage_only=True,
        autopublish_enabled=False,
        enable_autoupdate=bool(row.get("enable_autoupdate"))
        if row.get("enable_autoupdate") is not None
        else defaults.enable_autoupdate,
        update_interval_minutes=int(row.get("update_interval_minutes"))
        if row.get("update_interval_minutes") is not None
        else defaults.update_interval_minutes,
        dry_run_default=(
            bool(row.get("dry_run"))
            if row.get("dry_run") is not None
            else defaults.dry_run_default
        ),
        allowed_translation_types=allowed_types or defaults.allowed_translation_types,
        allowed_translations=_normalize_setting_list(
            row.get("allowed_translations", defaults.allowed_translations)
        ),
        allowed_qualities=_normalize_setting_list(
            row.get("allowed_qualities", defaults.allowed_qualities)
        ),
        preferred_translation_priority=_normalize_setting_list(
            row.get("preferred_translation_priority", defaults.preferred_translation_priority)
        ),
        preferred_quality_priority=_normalize_setting_list(
            row.get("preferred_quality_priority", defaults.preferred_quality_priority)
        ),
        blacklist_titles=_normalize_setting_list(
            row.get("blacklist_titles", defaults.blacklist_titles)
        ),
        blacklist_external_ids=_normalize_setting_list(
            row.get("blacklist_external_ids", defaults.blacklist_external_ids)
        ),
    )


async def get_parser_settings(session: AsyncSession) -> ParserSettings:
    result = await session.execute(select(parser_settings).limit(1))
    row = result.mappings().first()
    if row is not None:
        return _settings_from_row(row)
    settings = ParserSettings()
    await session.execute(
        insert(parser_settings).values(
            **_settings_to_row(settings),
            updated_at=datetime.now(timezone.utc),
        )
    )
    return settings


def _matches_blacklist(title: str | None, blacklist: Iterable[str]) -> bool:
    if not title:
        return False
    lowered = title.lower()
    return any(entry and entry in lowered for entry in blacklist)


def _filter_catalog(
    catalog: list[AnimeExternal], settings: ParserSettings
) -> list[AnimeExternal]:
    blacklist_titles = [item.lower() for item in settings.blacklist_titles if item]
    blacklist_ids = {item for item in settings.blacklist_external_ids if item}
    if not blacklist_titles and not blacklist_ids:
        return list(catalog)
    filtered: list[AnimeExternal] = []
    for anime in catalog:
        if str(anime.source_id) in blacklist_ids:
            continue
        if any(
            _matches_blacklist(title, blacklist_titles)
            for title in (anime.title, anime.title_ru, anime.title_en, anime.original_title)
        ):
            continue
        filtered.append(anime)
    return filtered


def _filter_schedule(
    schedule: list[ScheduleItem], allowed_anime_ids: set[str]
) -> tuple[list[ScheduleItem], int]:
    if not allowed_anime_ids:
        return [], len(schedule)
    filtered = [item for item in schedule if item.anime_source_id in allowed_anime_ids]
    return filtered, len(schedule) - len(filtered)


def _sort_by_priority(
    items: list[str], priority: list[str]
) -> list[str]:
    if not items:
        return []
    if not priority:
        return list(items)
    priority_map = {value.lower(): index for index, value in enumerate(priority)}
    indexed = list(enumerate(items))
    indexed.sort(
        key=lambda entry: (
            priority_map.get(entry[1].lower(), len(priority_map)),
            entry[0],
        )
    )
    return [item for _idx, item in indexed]


def _filter_episodes(
    episodes: list[EpisodeExternal],
    settings: ParserSettings,
    allowed_anime_ids: set[str],
) -> tuple[list[EpisodeExternal], int]:
    allowed_types = {item.lower() for item in settings.allowed_translation_types}
    allowed_translations = {item.lower() for item in settings.allowed_translations}
    allowed_qualities = {item.lower() for item in settings.allowed_qualities}
    filtered: list[EpisodeExternal] = []
    filtered_out = 0
    for episode in episodes:
        if allowed_anime_ids and episode.anime_source_id not in allowed_anime_ids:
            filtered_out += 1
            continue
        translations = list(episode.translations)
        if episode.translation and all(
            episode.translation != translation.name for translation in translations
        ):
            translations.append(
                TranslationExternal(
                    code=episode.translation, name=episode.translation, type=None
                )
            )
        has_translation_info = bool(translations)
        filtered_translations: list[TranslationExternal] = []
        for translation in translations:
            if (
                allowed_types
                and translation.type
                and translation.type.lower() not in allowed_types
            ):
                continue
            if allowed_translations:
                code = (translation.code or "").lower()
                name = (translation.name or "").lower()
                if code not in allowed_translations and name not in allowed_translations:
                    continue
            filtered_translations.append(translation)
        if (
            (allowed_types or allowed_translations)
            and has_translation_info
            and not filtered_translations
        ):
            filtered_out += 1
            continue
        translation_keys = [
            translation.name or translation.code
            for translation in filtered_translations
            if translation.name or translation.code
        ]
        translation_names = _sort_by_priority(
            translation_keys, settings.preferred_translation_priority
        )
        priority_map = {
            value.lower(): index
            for index, value in enumerate(settings.preferred_translation_priority)
        }
        indexed_translations = list(enumerate(filtered_translations))
        indexed_translations.sort(
            key=lambda entry: (
                priority_map.get(
                    (entry[1].name or entry[1].code or "").lower(),
                    len(priority_map),
                ),
                entry[0],
            )
        )
        ordered_translations = [item for _idx, item in indexed_translations]
        primary_translation = translation_names[0] if translation_names else None
        qualities = list(dict.fromkeys(episode.qualities))
        if episode.quality and episode.quality not in qualities:
            qualities.append(episode.quality)
        filtered_qualities = (
            [quality for quality in qualities if quality.lower() in allowed_qualities]
            if allowed_qualities
            else qualities
        )
        if allowed_qualities and not filtered_qualities:
            filtered_out += 1
            continue
        filtered_qualities = _sort_by_priority(
            filtered_qualities, settings.preferred_quality_priority
        )
        primary_quality = filtered_qualities[0] if filtered_qualities else None
        filtered.append(
            EpisodeExternal(
                anime_source_id=episode.anime_source_id,
                number=episode.number,
                title=episode.title,
                translation=primary_translation,
                quality=primary_quality,
                aired_at=episode.aired_at,
                stream_url=episode.stream_url,
                translations=[
                    TranslationExternal(
                        code=translation.code or translation.name or "",
                        name=translation.name or translation.code or "",
                        type=translation.type,
                    )
                    for translation in ordered_translations
                ],
                qualities=filtered_qualities,
            )
        )
    return filtered, filtered_out


class ParserSyncService:
    def __init__(
        self,
        catalog_source: CatalogSourcePort,
        episode_source: EpisodeSourcePort,
        schedule_source: ScheduleSourcePort,
        *,
        session: AsyncSession | None = None,
        anime_repo: AnimeExternalRepository | None = None,
        schedule_repo: ScheduleRepository | None = None,
        episode_repo: EpisodeExternalRepository | None = None,
    ) -> None:
        self._catalog_source = catalog_source
        self._episode_source = episode_source
        self._schedule_source = schedule_source
        self._session = session
        self._anime_repo = anime_repo
        self._schedule_repo = schedule_repo
        self._episode_repo = episode_repo
        if session is not None:
            self._anime_repo = self._anime_repo or AnimeExternalRepository(session)
            self._schedule_repo = self._schedule_repo or ScheduleRepository(session)
            self._episode_repo = self._episode_repo or EpisodeExternalRepository(session)

    async def sync_catalog(self) -> list[AnimeExternal]:
        return list(await self._catalog_source.fetch_catalog())

    async def sync_episodes(self) -> list[EpisodeExternal]:
        return list(await self._episode_source.fetch_episodes())

    async def sync_schedule(self) -> list[ScheduleItem]:
        return list(await self._schedule_source.fetch_schedule())

    async def sync_all(
        self, *, persist: bool = True, publish: bool = False
    ) -> list[dict[str, object]] | dict[str, object]:
        if not persist or self._session is None:
            catalog = list(await self._catalog_source.fetch_catalog())
            schedule = list(await self._schedule_source.fetch_schedule())
            episodes = list(await self._episode_source.fetch_episodes())
            schedule_by_anime: dict[str, list] = {}
            for item in schedule:
                schedule_by_anime.setdefault(item.anime_source_id, []).append(item)
            episodes_by_anime: dict[str, list] = {}
            for episode in episodes:
                episodes_by_anime.setdefault(episode.anime_source_id, []).append(episode)
            return [
                {
                    "anime": anime,
                    "schedule": schedule_by_anime.get(anime.source_id, []),
                    "episodes": episodes_by_anime.get(anime.source_id, []),
                }
                for anime in catalog
            ]
        return await self._sync_all_persisted(publish=publish)

    async def _sync_all_persisted(self, *, publish: bool) -> dict[str, object]:
        summary: dict[str, Any] = {
            "catalog": {"fetched": 0, "persisted": 0, "skipped": 0},
            "schedule": {"fetched": 0, "persisted": 0, "skipped": 0},
            "episodes": {"fetched": 0, "persisted": 0, "skipped": 0},
            "errors": [],
        }
        if publish:
            summary["errors"].append(
                {"source": "publish", "message": "Publishing is disabled in staging mode"}
            )
        catalog_error: Exception | None = None
        schedule_error: Exception | None = None
        episode_error: Exception | None = None
        try:
            catalog = await self.sync_catalog()
        except Exception as exc:  # pragma: no cover - defensive
            catalog = []
            catalog_error = exc
            summary["errors"].append({"source": "catalog", "message": str(exc)})
        try:
            schedule = await self.sync_schedule()
        except Exception as exc:  # pragma: no cover - defensive
            schedule = []
            schedule_error = exc
            summary["errors"].append({"source": "schedule", "message": str(exc)})
        try:
            episodes = await self.sync_episodes()
        except Exception as exc:  # pragma: no cover - defensive
            episodes = []
            episode_error = exc
            summary["errors"].append({"source": "episodes", "message": str(exc)})
        summary["catalog"]["fetched"] = len(catalog)
        summary["schedule"]["fetched"] = len(schedule)
        summary["episodes"]["fetched"] = len(episodes)
        session = self._session
        if session is None:
            return summary
        source_ids = await self._ensure_sources(session)
        settings = await self._ensure_settings(session)
        now = datetime.now(timezone.utc)
        anime_map: dict[str, int] = {}
        filtered_catalog = _filter_catalog(catalog, settings)
        catalog_filtered_out = len(catalog) - len(filtered_catalog)
        summary["catalog"]["skipped"] = catalog_filtered_out
        allowed_anime_ids = {anime.source_id for anime in filtered_catalog}
        filtered_schedule, schedule_filtered_out = _filter_schedule(
            schedule, allowed_anime_ids
        )
        filtered_episodes, episode_filtered_out = _filter_episodes(
            episodes, settings, allowed_anime_ids
        )
        catalog_result, catalog_error_message = await self._run_job(
            session,
            source_ids["shikimori"],
            "catalog_sync",
            catalog_error,
            lambda: self._persist_catalog(
                source_ids["shikimori"], filtered_catalog, seen_at=now
            ),
        )
        if catalog_error_message:
            summary["errors"].append(
                {"source": "catalog", "message": catalog_error_message}
            )
        if catalog_result is not None:
            anime_map = catalog_result
            summary["catalog"]["persisted"] = len(anime_map)
        schedule_counts, schedule_error_message = await self._run_job(
            session,
            source_ids["shikimori"],
            "schedule_sync",
            schedule_error,
            lambda: self._persist_schedule(
                source_ids["shikimori"], filtered_schedule, anime_map, checked_at=now
            ),
        )
        if schedule_error_message:
            summary["errors"].append(
                {"source": "schedule", "message": schedule_error_message}
            )
        if schedule_counts is not None:
            persisted, skipped = schedule_counts
            summary["schedule"]["persisted"] = persisted
            summary["schedule"]["skipped"] = skipped + schedule_filtered_out
        episode_counts, episode_error_message = await self._run_job(
            session,
            source_ids["kodik"],
            "episode_sync",
            episode_error,
            lambda: self._persist_episodes(
                source_ids["kodik"], filtered_episodes, anime_map, updated_at=now
            ),
        )
        if episode_error_message:
            summary["errors"].append(
                {"source": "episodes", "message": episode_error_message}
            )
        if episode_counts is not None:
            persisted, skipped, _translation_count = episode_counts
            summary["episodes"]["persisted"] = persisted
            summary["episodes"]["skipped"] = skipped + episode_filtered_out
        await _commit(session)
        return summary

    async def _ensure_sources(self, session: AsyncSession) -> dict[str, int]:
        insert_fn = _insert_for(session)
        rows = [
            {
                "code": "shikimori",
                "enabled": True,
                "rate_limit_per_min": 60,
                "max_concurrency": 2,
            },
            {
                "code": "kodik",
                "enabled": True,
                "rate_limit_per_min": 60,
                "max_concurrency": 2,
            },
        ]
        stmt = insert_fn(parser_sources).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["code"])
        await session.execute(stmt)
        result = await session.execute(
            select(parser_sources.c.id, parser_sources.c.code).where(
                parser_sources.c.code.in_(["shikimori", "kodik"])
            )
        )
        return {row.code: row.id for row in result}

    async def _ensure_settings(self, session: AsyncSession) -> ParserSettings:
        return await get_parser_settings(session)

    async def _run_job(
        self,
        session: AsyncSession,
        source_id: int,
        job_type: str,
        existing_error: Exception | None,
        action: Callable[[], Any],
    ) -> tuple[Any | None, str | None]:
        if existing_error is not None:
            await self._fail_job(session, source_id, job_type, existing_error)
            return None, str(existing_error)
        job_id = await self._create_job(session, source_id, job_type)
        try:
            result = await action()
        except Exception as exc:  # pragma: no cover - defensive
            await session.rollback()
            await self._log_job(session, job_id, "error", str(exc))
            await self._finish_job(session, job_id, source_id, "failed", str(exc))
            return None, str(exc)
        await self._finish_job(session, job_id, source_id, "success", None)
        return result, None

    async def _fail_job(
        self, session: AsyncSession, source_id: int, job_type: str, error: Exception
    ) -> None:
        job_id = await self._create_job(session, source_id, job_type)
        await self._log_job(session, job_id, "error", str(error))
        await self._finish_job(session, job_id, source_id, "failed", str(error))

    async def _create_job(
        self, session: AsyncSession, source_id: int, job_type: str
    ) -> int:
        stmt = (
            insert(parser_jobs)
            .values(
                source_id=source_id,
                job_type=job_type,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            .returning(parser_jobs.c.id)
        )
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def _finish_job(
        self,
        session: AsyncSession,
        job_id: int,
        source_id: int,
        status: str,
        error_summary: str | None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        await session.execute(
            update(parser_jobs)
            .where(parser_jobs.c.id == job_id)
            .values(status=status, finished_at=finished_at, error_summary=error_summary)
        )
        if status == "success":
            await session.execute(
                update(parser_sources)
                .where(parser_sources.c.id == source_id)
                .values(last_synced_at=finished_at)
            )

    async def _log_job(
        self, session: AsyncSession, job_id: int, level: str, message: str
    ) -> None:
        await session.execute(
            insert(parser_job_logs).values(
                job_id=job_id,
                level=level,
                message=message,
                created_at=datetime.now(timezone.utc),
            )
        )

    async def _persist_catalog(
        self, source_id: int, catalog: list[AnimeExternal], *, seen_at: datetime
    ) -> dict[str, int]:
        if self._anime_repo is None:
            return {}
        return await self._anime_repo.upsert_many(
            source_id, catalog, seen_at=seen_at
        )

    async def _persist_schedule(
        self,
        source_id: int,
        schedule: list[ScheduleItem],
        anime_map: dict[str, int],
        *,
        checked_at: datetime,
    ) -> tuple[int, int]:
        if self._schedule_repo is None:
            return 0, len(schedule)
        return await self._schedule_repo.upsert_many(
            source_id, schedule, anime_map, checked_at=checked_at
        )

    async def _persist_episodes(
        self,
        source_id: int,
        episodes: list[EpisodeExternal],
        anime_map: dict[str, int],
        *,
        updated_at: datetime,
    ) -> tuple[int, int, int]:
        if self._episode_repo is None:
            return 0, len(episodes), 0
        return await self._episode_repo.upsert_many(
            source_id, episodes, anime_map, updated_at=updated_at
        )
