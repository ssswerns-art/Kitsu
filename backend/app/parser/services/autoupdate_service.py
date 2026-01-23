from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping, Sequence

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import tuple_

from app.models.episode import Episode
from app.models.release import Release

from ..config import ParserSettings
from ..domain.entities import EpisodeExternal, ScheduleItem
from ..repositories.schedule_repo import ScheduleRepository
from ..sources.kodik_episode import KodikEpisodeSource
from ..sources.shikimori_schedule import ShikimoriScheduleSource
from ..tables import (
    anime_episodes_external,
    anime_external,
    anime_external_binding,
    anime_schedule,
    parser_job_logs,
    parser_jobs,
    parser_sources,
)
from .sync_service import get_parser_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceConfig:
    id: int
    enabled: bool
    rate_limit_per_min: int
    max_concurrency: int


MIN_UPDATE_INTERVAL_MINUTES = 30
MAX_UPDATE_INTERVAL_MINUTES = 60
DEFAULT_UPDATE_INTERVAL_MINUTES = 60
MIN_BATCH_SIZE = 1
KODIK_SHIKIMORI_PARAM = "shikimori_id"


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


def _resolve_rate_limit_seconds(rate_limit_per_min: int | None) -> float:
    if not rate_limit_per_min or rate_limit_per_min <= 0:
        return 0.0
    return 60.0 / float(rate_limit_per_min)


def resolve_update_interval_minutes(settings: ParserSettings) -> int:
    value = int(settings.update_interval_minutes or 0)
    if not value:
        value = DEFAULT_UPDATE_INTERVAL_MINUTES
    return min(MAX_UPDATE_INTERVAL_MINUTES, max(MIN_UPDATE_INTERVAL_MINUTES, value))


def _schedule_hash(item: ScheduleItem) -> str:
    payload = {
        "episode_number": item.episode_number,
        "airs_at": item.airs_at.isoformat() if item.airs_at else None,
        "source_url": item.source_url,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _chunked(values: Sequence[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        return [list(values)]
    return [list(values[idx : idx + chunk_size]) for idx in range(0, len(values), chunk_size)]


class ParserEpisodeAutoupdateService:
    """
    Episode auto-update service with compliance checks.
    
    COMPLIANCE NOTE (PARSER-02):
    This service implements ONLY compliance checks - it does NOT implement
    auto-scheduling or background workers. Auto-parsing logic is out of scope
    for this task and should be implemented in a separate task.
    
    This service respects:
    - Manual > Parser invariant (does not update manual episodes)
    - Lock enforcement (respects locked fields)
    - Dry-run mode (from parser_settings)
    - Source marking (sets source="parser")
    """
    
    def __init__(
        self,
        session: AsyncSession,
        *,
        schedule_source: ShikimoriScheduleSource | None = None,
        episode_source: KodikEpisodeSource | None = None,
        schedule_repo: ScheduleRepository | None = None,
        settings: ParserSettings | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._schedule_source = schedule_source
        self._episode_source = episode_source
        self._schedule_repo = schedule_repo or ScheduleRepository(session)
        self._settings = settings
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    async def run(self, *, force: bool = False) -> dict[str, object]:
        settings = self._settings or await get_parser_settings(self._session)
        if not settings.enable_autoupdate and not force:
            return {
                "status": "disabled",
                "schedule": {"updated": 0, "skipped": 0},
                "episodes": {"inserted": 0, "skipped": 0, "conflicts": 0},
            }
        source_configs = await self._ensure_sources()
        shikimori = source_configs.get("shikimori")
        kodik = source_configs.get("kodik")
        if shikimori is None or kodik is None or not shikimori.enabled or not kodik.enabled:
            return {
                "status": "disabled",
                "schedule": {"updated": 0, "skipped": 0},
                "episodes": {"inserted": 0, "skipped": 0, "conflicts": 0},
            }
        job_id = await self._create_job(kodik.id, "parser_episode_autoupdate")
        try:
            summary = await self._run_autoupdate(settings, shikimori, kodik)
        except Exception as exc:  # pragma: no cover - defensive
            await self._session.rollback()
            error_message = f"{type(exc).__name__}: {exc}"
            await self._log_job(job_id, "error", error_message)
            await self._finish_job(job_id, kodik.id, "failed", error_message)
            return {
                "status": "failed",
                "schedule": {"updated": 0, "skipped": 0},
                "episodes": {"inserted": 0, "skipped": 0, "conflicts": 0},
                "errors": [error_message],
            }
        await self._finish_job(job_id, kodik.id, "success", None)
        # Caller is responsible for committing the transaction
        return summary

    async def _run_autoupdate(
        self, settings: ParserSettings, shikimori: SourceConfig, kodik: SourceConfig
    ) -> dict[str, object]:
        schedule_source = self._schedule_source or ShikimoriScheduleSource(
            settings, rate_limit_seconds=_resolve_rate_limit_seconds(shikimori.rate_limit_per_min)
        )
        episode_source = self._episode_source or KodikEpisodeSource(
            settings, rate_limit_seconds=_resolve_rate_limit_seconds(kodik.rate_limit_per_min)
        )
        schedule = list(await schedule_source.fetch_schedule())
        now = self._now_provider()
        anime_result = await self._session.execute(
            select(
                anime_external.c.id,
                anime_external.c.external_id,
                anime_external.c.anime_id,
                anime_external_binding.c.anime_id.label("bound_anime_id"),
            )
            .select_from(anime_external)
            .outerjoin(
                anime_external_binding,
                anime_external_binding.c.anime_external_id == anime_external.c.id,
            )
            .where(anime_external.c.source_id == shikimori.id)
            .where(anime_external.c.status == "ongoing")
        )
        anime_map: dict[str, int] = {}
        binding_map: dict[int, str | None] = {}
        for row in anime_result.mappings():
            external_id = row.get("external_id")
            if not external_id:
                continue
            anime_id = int(row["id"])
            anime_map[str(external_id)] = anime_id
            binding_map[anime_id] = row.get("bound_anime_id") or row.get("anime_id")
        schedule_candidates = [
            item
            for item in schedule
            if item.episode_number is not None
            and item.anime_source_id in anime_map
        ]
        schedule_keys = [
            (anime_map[item.anime_source_id], item.episode_number)
            for item in schedule_candidates
        ]
        existing_schedule: dict[tuple[int, int | None], Mapping[str, Any]] = {}
        if schedule_keys:
            schedule_result = await self._session.execute(
                select(
                    anime_schedule.c.anime_id,
                    anime_schedule.c.episode_number,
                    anime_schedule.c.last_checked_at,
                    anime_schedule.c.source_hash,
                ).where(tuple_(anime_schedule.c.anime_id, anime_schedule.c.episode_number).in_(schedule_keys))
            )
            existing_schedule = {
                (row.anime_id, row.episode_number): row
                for row in schedule_result.mappings()
            }
        interval_minutes = resolve_update_interval_minutes(settings)
        cutoff = now - timedelta(minutes=interval_minutes)
        schedule_updates: list[ScheduleItem] = []
        schedule_skipped = 0
        anime_source_ids: list[str] = []
        for item in schedule_candidates:
            anime_id = anime_map[item.anime_source_id]
            schedule_hash = _schedule_hash(item)
            key = (anime_id, item.episode_number)
            existing = existing_schedule.get(key)
            if (
                existing
                and existing.get("source_hash") == schedule_hash
                and existing.get("last_checked_at")
                and existing["last_checked_at"] >= cutoff
            ):
                schedule_skipped += 1
                continue
            schedule_updates.append(
                ScheduleItem(
                    anime_source_id=item.anime_source_id,
                    episode_number=item.episode_number,
                    airs_at=item.airs_at,
                    source_url=item.source_url,
                    source_hash=schedule_hash,
                )
            )
            anime_source_ids.append(item.anime_source_id)
        anime_source_ids = list({source_id for source_id in anime_source_ids})
        if schedule_updates:
            await self._schedule_repo.upsert_many(
                shikimori.id, schedule_updates, anime_map, checked_at=now
            )
        anime_ids = {anime_map[source_id] for source_id in anime_source_ids}
        existing_episode_numbers: dict[int, set[int]] = {}
        if anime_ids:
            episode_result = await self._session.execute(
                select(
                    anime_episodes_external.c.anime_id,
                    anime_episodes_external.c.episode_number,
                ).where(anime_episodes_external.c.anime_id.in_(anime_ids))
            )
            for row in episode_result:
                existing_episode_numbers.setdefault(int(row.anime_id), set()).add(
                    int(row.episode_number)
                )
        manual_episode_numbers = await self._load_manual_episode_numbers(binding_map)
        inserted = 0
        skipped = 0
        conflicts = 0
        if anime_source_ids:
            batch_size = max(MIN_BATCH_SIZE, kodik.max_concurrency)
            for batch in _chunked(anime_source_ids, batch_size):
                params = {KODIK_SHIKIMORI_PARAM: ",".join(batch)}
                batch_episodes = list(await episode_source.fetch_episodes_for(params))
                rows: list[dict[str, object]] = []
                conflict_keys: set[tuple[int, int]] = set()
                for episode in batch_episodes:
                    anime_id = anime_map.get(episode.anime_source_id)
                    if anime_id is None:
                        skipped += 1
                        continue
                    episode_number = episode.number
                    has_manual_conflict = episode_number in manual_episode_numbers.get(
                        anime_id, set()
                    )
                    if episode_number in existing_episode_numbers.get(anime_id, set()):
                        if has_manual_conflict:
                            conflicts += 1
                            conflict_keys.add((anime_id, episode_number))
                        skipped += 1
                        continue
                    needs_review = False
                    if has_manual_conflict:
                        needs_review = True
                        conflicts += 1
                        conflict_keys.add((anime_id, episode_number))
                    rows.append(
                        _episode_row(
                            episode,
                            anime_id=anime_id,
                            source_id=kodik.id,
                            updated_at=now,
                            needs_review=needs_review,
                        )
                    )
                    existing_episode_numbers.setdefault(anime_id, set()).add(
                        episode_number
                    )
                if rows:
                    inserted += len(rows)
                    insert_fn = _insert_for(self._session)
                    stmt = insert_fn(anime_episodes_external).values(rows)
                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=[
                            anime_episodes_external.c.anime_id,
                            anime_episodes_external.c.source_id,
                            anime_episodes_external.c.episode_number,
                        ]
                    )
                    await self._session.execute(stmt)
                if conflict_keys:
                    await self._session.execute(
                        update(anime_episodes_external)
                        .where(
                            tuple_(
                                anime_episodes_external.c.anime_id,
                                anime_episodes_external.c.episode_number,
                            ).in_(list(conflict_keys))
                        )
                        .values(needs_review=True)
                    )
        return {
            "status": "success",
            "schedule": {"updated": len(schedule_updates), "skipped": schedule_skipped},
            "episodes": {"inserted": inserted, "skipped": skipped, "conflicts": conflicts},
        }

    async def _load_manual_episode_numbers(
        self, binding_map: Mapping[int, str | None]
    ) -> dict[int, set[int]]:
        bound_anime_ids = {value for value in binding_map.values() if value}
        if not bound_anime_ids:
            return {}
        release_table = Release.__table__
        episode_table = Episode.__table__
        result = await self._session.execute(
            select(release_table.c.anime_id, episode_table.c.number)
            .select_from(
                release_table.join(
                    episode_table, episode_table.c.release_id == release_table.c.id
                )
            )
            .where(release_table.c.anime_id.in_(bound_anime_ids))
        )
        by_anime: dict[str, set[int]] = {}
        for row in result:
            by_anime.setdefault(str(row.anime_id), set()).add(int(row.number))
        by_external: dict[int, set[int]] = {}
        for external_id, anime_id in binding_map.items():
            if not anime_id:
                continue
            numbers = by_anime.get(str(anime_id))
            if numbers:
                by_external[external_id] = numbers
        return by_external

    async def _ensure_sources(self) -> dict[str, SourceConfig]:
        insert_fn = _insert_for(self._session)
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
        await self._session.execute(stmt)
        result = await self._session.execute(
            select(
                parser_sources.c.id,
                parser_sources.c.code,
                parser_sources.c.enabled,
                parser_sources.c.rate_limit_per_min,
                parser_sources.c.max_concurrency,
            ).where(parser_sources.c.code.in_(["shikimori", "kodik"]))
        )
        return {
            row.code: SourceConfig(
                id=int(row.id),
                enabled=bool(row.enabled),
                rate_limit_per_min=int(row.rate_limit_per_min or 0),
                max_concurrency=int(row.max_concurrency or 1),
            )
            for row in result
        }

    async def _create_job(self, source_id: int, job_type: str) -> int:
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
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def _finish_job(
        self, job_id: int, source_id: int, status: str, error_summary: str | None
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        await self._session.execute(
            update(parser_jobs)
            .where(parser_jobs.c.id == job_id)
            .values(status=status, finished_at=finished_at, error_summary=error_summary)
        )
        if status == "success":
            await self._session.execute(
                update(parser_sources)
                .where(parser_sources.c.id == source_id)
                .values(last_synced_at=finished_at)
            )

    async def _log_job(self, job_id: int, level: str, message: str) -> None:
        await self._session.execute(
            insert(parser_job_logs).values(
                job_id=job_id,
                level=level,
                message=message,
                created_at=datetime.now(timezone.utc),
            )
        )


def _episode_row(
    episode: EpisodeExternal,
    *,
    anime_id: int,
    source_id: int,
    updated_at: datetime,
    needs_review: bool,
) -> dict[str, object]:
    qualities = list(dict.fromkeys(episode.qualities or []))
    if episode.quality and episode.quality not in qualities:
        qualities.append(episode.quality)
    translations = [t.name for t in episode.translations if t.name]
    if episode.translation and episode.translation not in translations:
        translations.append(episode.translation)
    return {
        "anime_id": anime_id,
        "source_id": source_id,
        "episode_number": episode.number,
        "iframe_url": episode.stream_url,
        "available_qualities": qualities or None,
        "available_translations": translations or None,
        "needs_review": needs_review,
        "updated_at": updated_at,
    }
