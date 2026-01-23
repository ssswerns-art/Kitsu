from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.anime import Anime
from app.models.episode import Episode
from app.models.release import Release
from app.services.admin.lock_service import LockService
from app.services.audit.audit_service import AuditService

from ..config import ParserSettings
from ..domain.errors import (
    ParserCannotOverrideManualError,
)
from ..repositories.anime_external_binding_repo import AnimeExternalBindingRepository
from ..tables import (
    anime_episodes_external,
    anime_external,
    anime_translations,
    parser_settings,
)
from .sync_service import _settings_from_row

logger = logging.getLogger(__name__)


class PublishNotFoundError(RuntimeError):
    pass


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _clean_poster_url(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    parts = urlsplit(trimmed)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _sort_by_priority(items: list[str], priority: list[str]) -> list[str]:
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


# Parser allowed states (contract requirement)
PARSER_ALLOWED_STATES = {"draft", "pending", "broken"}


class ParserPublishService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        binding_repo: AnimeExternalBindingRepository | None = None,
        audit_service: AuditService | None = None,
    ) -> None:
        self._session = session
        self._binding_repo = binding_repo or AnimeExternalBindingRepository(session)
        self._audit_service = audit_service or AuditService(session)
        self._anime_table = Anime.__table__
        self._release_table = Release.__table__
        self._episode_table = Episode.__table__

    async def publish_anime(
        self, anime_external_id: int, *, bound_by: str = "admin"
    ) -> dict[str, object]:
        # Get parser settings to check dry-run mode
        settings = await self._get_settings()
        
        external_row = await self._get_anime_external(anime_external_id)
        if external_row is None:
            raise PublishNotFoundError("Anime external not found")
        payload = self._build_anime_payload(external_row)
        binding = await self._binding_repo.get_by_external_id(anime_external_id)
        binding_anime_id = binding.get("anime_id") if binding else None
        anime_id = _parse_uuid(binding_anime_id) if binding_anime_id else None
        if anime_id is None:
            anime_id = _parse_uuid(external_row.get("anime_id"))
        if anime_id is None:
            anime_id = uuid.uuid4()
        current = await self._get_anime_payload(anime_id)
        created = current is None
        
        # Get existing anime to check compliance (if exists)
        existing_anime = None
        if not created:
            existing_anime = await self._get_anime_entity(anime_id)
        
        # COMPLIANCE CHECK 1: Manual > Parser invariant
        if existing_anime and existing_anime.source == "manual":
            logger.warning(
                f"[PARSER COMPLIANCE] Cannot update anime {anime_id}: source='manual'"
            )
            raise ParserCannotOverrideManualError(
                f"Cannot update anime {anime_id}: source is 'manual'"
            )
        
        # COMPLIANCE CHECK 2: Lock check
        if existing_anime and existing_anime.is_locked:
            fields_to_update = list(payload.keys())
            try:
                LockService.check_parser_update(
                    entity=existing_anime,
                    fields_to_update=fields_to_update,
                    actor_type="system",
                )
            except Exception as exc:
                logger.exception(
                    f"[PARSER COMPLIANCE] Cannot update anime {anime_id}: {exc}"
                )
                raise
        
        # COMPLIANCE CHECK 3: Dry-run mode
        if settings.dry_run_default:
            logger.info(
                f"[DRY-RUN] Would {'create' if created else 'update'} anime {anime_id}"
            )
            logger.info(f"[DRY-RUN] Payload: {payload}")
            return {"anime_id": str(anime_id), "created": created, "dry_run": True}
        
        # Save before state for audit
        before_state = LockService.serialize_entity(existing_anime) if existing_anime else None
        
        # Perform the update
        await self._upsert_anime(anime_id, payload)
        if binding is None:
            await self._binding_repo.ensure_binding(
                anime_external_id,
                str(anime_id),
                bound_by=bound_by,
            )
        
        # COMPLIANCE CHECK 4: Audit logging (MANDATORY)
        # NOTE: Audit logging MUST happen BEFORE commit to ensure atomicity
        after_state = {**payload, "id": str(anime_id)}
        if created:
            await self._audit_service.log_create(
                entity_type="anime",
                entity_id=str(anime_id),
                entity_data=after_state,
                actor=None,
                actor_type="system",
                reason=f"Automatic sync from external source {anime_external_id}",
            )
        else:
            # Only log changed fields
            changed_before = {
                k: v for k, v in (before_state or {}).items() 
                if k in payload and v != payload.get(k)
            }
            changed_after = {
                k: v for k, v in payload.items()
                if k in changed_before or before_state is None or before_state.get(k) != v
            }
            
            await self._audit_service.log_update(
                entity_type="anime",
                entity_id=str(anime_id),
                before_data=changed_before,
                after_data=changed_after,
                actor=None,
                actor_type="system",
                reason=f"Automatic sync from external source {anime_external_id}",
            )
        
        # Caller is responsible for committing the transaction
        logger.info(f"[PARSER] Successfully {'created' if created else 'updated'} anime {anime_id}")
        return {"anime_id": str(anime_id), "created": created}

    async def publish_episode(
        self, anime_id: str, episode_number: int
    ) -> dict[str, object]:
        # Get parser settings to check dry-run mode
        settings = await self._get_settings()
        
        parsed_id = _parse_uuid(anime_id)
        if parsed_id is None:
            raise PublishNotFoundError("Anime not found")
        binding = await self._binding_repo.get_by_anime_id(str(parsed_id))
        binding_external_id = binding.get("anime_external_id") if binding else None
        if binding_external_id is None:
            raise PublishNotFoundError("Anime binding not found")
        external_episode = await self._get_episode_external(
            int(binding_external_id), episode_number
        )
        if external_episode is None:
            raise PublishNotFoundError("Episode external not found")
        anime_row = await self._get_anime_row(parsed_id)
        if anime_row is None:
            raise PublishNotFoundError("Anime not found")
        
        # COMPLIANCE CHECK 1: Check if anime is manual (shouldn't publish episodes for manual anime)
        if anime_row.get("source") == "manual":
            logger.warning(
                f"[PARSER COMPLIANCE] Cannot publish episode for manual anime {anime_id}"
            )
            raise ParserCannotOverrideManualError(
                f"Cannot publish episode for anime {anime_id}: anime source is 'manual'"
            )
        
        translation_types = await self._get_translation_types(int(binding_external_id))
        translations = self._filter_translations(
            external_episode.get("available_translations"),
            translation_types,
            settings,
        )
        qualities = self._filter_qualities(
            external_episode.get("available_qualities"),
            settings,
        )
        release_id = await self._ensure_release(parsed_id, anime_row)
        
        # Get existing episode to check compliance
        existing_episode = await self._get_episode_entity(release_id, episode_number)
        created = existing_episode is None
        
        # COMPLIANCE CHECK 2: Manual > Parser for episodes
        if existing_episode and existing_episode.source == "manual":
            logger.warning(
                f"[PARSER COMPLIANCE] Cannot update episode {episode_number} of anime {anime_id}: source='manual'"
            )
            raise ParserCannotOverrideManualError(
                f"Cannot update episode {episode_number}: source is 'manual'"
            )
        
        # COMPLIANCE CHECK 3: Lock check for episodes
        if existing_episode and existing_episode.is_locked:
            fields_to_update = ["iframe_url", "available_translations", "available_qualities"]
            try:
                LockService.check_parser_update(
                    entity=existing_episode,
                    fields_to_update=fields_to_update,
                    actor_type="system",
                )
            except Exception as exc:
                logger.exception(
                    f"[PARSER COMPLIANCE] Cannot update episode {episode_number}: {exc}"
                )
                raise
        
        # COMPLIANCE CHECK 4: Dry-run mode
        if settings.dry_run_default:
            logger.info(
                f"[DRY-RUN] Would {'create' if created else 'update'} episode "
                f"{episode_number} for anime {anime_id}"
            )
            logger.info(
                f"[DRY-RUN] iframe_url={external_episode.get('iframe_url')}, "
                f"translations={translations}, qualities={qualities}"
            )
            return {"episode_id": str(uuid.uuid4()), "created": created, "dry_run": True}
        
        # Save before state for audit
        before_state = LockService.serialize_entity(existing_episode) if existing_episode else None
        
        # Perform the update
        episode_id, created = await self._upsert_episode(
            release_id,
            episode_number,
            external_episode.get("iframe_url"),
            translations,
            qualities,
        )
        
        # COMPLIANCE CHECK 5: Audit logging (MANDATORY)
        # NOTE: Audit logging MUST happen BEFORE commit to ensure atomicity
        after_state = {
            "id": str(episode_id),
            "release_id": str(release_id),
            "number": episode_number,
            "iframe_url": external_episode.get("iframe_url"),
            "available_translations": translations,
            "available_qualities": qualities,
        }
        
        if created:
            await self._audit_service.log_create(
                entity_type="episode",
                entity_id=str(episode_id),
                entity_data=after_state,
                actor=None,
                actor_type="system",
                reason=f"Automatic sync from external source {binding_external_id}",
            )
        else:
            # Only log changed fields
            changed_before = {
                k: v for k, v in (before_state or {}).items()
                if k in after_state and v != after_state.get(k)
            }
            changed_after = {
                k: v for k, v in after_state.items()
                if k in changed_before or before_state is None or before_state.get(k) != v
            }
            
            await self._audit_service.log_update(
                entity_type="episode",
                entity_id=str(episode_id),
                before_data=changed_before,
                after_data=changed_after,
                actor=None,
                actor_type="system",
                reason=f"Automatic sync from external source {binding_external_id}",
            )
        
        # Caller is responsible for committing the transaction
        logger.info(
            f"[PARSER] Successfully {'created' if created else 'updated'} "
            f"episode {episode_number} for anime {anime_id}"
        )
        return {"episode_id": str(episode_id), "created": created}

    async def unpublish_episode(self, anime_id: str, episode_number: int) -> bool:
        parsed_id = _parse_uuid(anime_id)
        if parsed_id is None:
            return False
        release_id = await self._get_release_id(parsed_id)
        if release_id is None:
            return False
        await self._session.execute(
            delete(self._episode_table).where(
                self._episode_table.c.release_id == release_id,
                self._episode_table.c.number == episode_number,
            )
        )
        # Caller is responsible for committing the transaction
        return True

    async def preview_diff(self, anime_external_id: int) -> dict[str, object]:
        external_row = await self._get_anime_external(anime_external_id)
        if external_row is None:
            raise PublishNotFoundError("Anime external not found")
        binding = await self._binding_repo.get_by_external_id(anime_external_id)
        anime_id = binding.get("anime_id") if binding else None
        current_payload = None
        if anime_id:
            parsed_id = _parse_uuid(anime_id)
            if parsed_id:
                current_payload = await self._get_anime_payload(parsed_id)
        external_payload = self._build_anime_payload(external_row)
        changes = [
            key
            for key, value in external_payload.items()
            if current_payload is None or current_payload.get(key) != value
        ]
        return {
            "anime_external_id": anime_external_id,
            "anime_id": anime_id,
            "external": external_payload,
            "current": current_payload,
            "changes": changes,
        }

    async def _get_anime_external(
        self, anime_external_id: int
    ) -> Mapping[str, object] | None:
        result = await self._session.execute(
            select(anime_external).where(anime_external.c.id == anime_external_id)
        )
        return result.mappings().first()

    def _build_anime_payload(self, row: Mapping[str, object]) -> dict[str, object]:
        title = (
            row.get("title_ru")
            or row.get("title_en")
            or row.get("title_original")
            or row.get("title_raw")
            or row.get("external_id")
        )
        genres = row.get("genres")
        return {
            "title": title,
            "title_ru": row.get("title_ru"),
            "title_en": row.get("title_en"),
            "title_original": row.get("title_original"),
            "description": row.get("description"),
            "poster_url": _clean_poster_url(row.get("poster_url")),
            "year": row.get("year"),
            "season": row.get("season"),
            "status": row.get("status"),
            "genres": list(genres) if genres else None,
        }

    async def _get_anime_payload(
        self, anime_id: uuid.UUID
    ) -> dict[str, object] | None:
        row = await self._get_anime_row(anime_id)
        if row is None:
            return None
        return {
            "title": row["title"],
            "title_ru": row["title_ru"],
            "title_en": row["title_en"],
            "title_original": row["title_original"],
            "description": row["description"],
            "poster_url": row["poster_url"],
            "year": row["year"],
            "season": row["season"],
            "status": row["status"],
            "genres": list(row["genres"]) if row["genres"] else None,
        }

    async def _get_anime_row(
        self, anime_id: uuid.UUID
    ) -> Mapping[str, object] | None:
        result = await self._session.execute(
            select(self._anime_table).where(self._anime_table.c.id == anime_id)
        )
        return result.mappings().first()
    
    async def _get_anime_entity(self, anime_id: uuid.UUID) -> Anime | None:
        """Get anime entity for compliance checks."""
        result = await self._session.execute(
            select(Anime).where(Anime.id == anime_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_episode_entity(
        self, release_id: uuid.UUID, episode_number: int
    ) -> Episode | None:
        """Get episode entity for compliance checks."""
        result = await self._session.execute(
            select(Episode).where(
                Episode.release_id == release_id,
                Episode.number == episode_number,
            )
        )
        return result.scalar_one_or_none()

    async def _upsert_anime(
        self, anime_id: uuid.UUID, payload: Mapping[str, object]
    ) -> None:
        insert_fn = _insert_for(self._session)
        
        # COMPLIANCE: Parser MUST set source="parser" and updated_by=NULL
        compliance_fields = {
            "source": "parser",
            "updated_by": None,
        }
        
        stmt = insert_fn(self._anime_table).values(
            id=anime_id,
            **payload,
            **compliance_fields,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": stmt.excluded.title,
                "title_ru": stmt.excluded.title_ru,
                "title_en": stmt.excluded.title_en,
                "title_original": stmt.excluded.title_original,
                "description": stmt.excluded.description,
                "poster_url": stmt.excluded.poster_url,
                "year": stmt.excluded.year,
                "season": stmt.excluded.season,
                "status": stmt.excluded.status,
                "genres": stmt.excluded.genres,
                # COMPLIANCE: Always set these on update
                "source": "parser",
                "updated_by": None,
            },
        )
        await self._session.execute(stmt)

    async def _ensure_release(
        self, anime_id: uuid.UUID, anime_row: Mapping[str, object]
    ) -> uuid.UUID:
        result = await self._session.execute(
            select(self._release_table.c.id)
            .where(self._release_table.c.anime_id == anime_id)
            .order_by(self._release_table.c.created_at.asc())
        )
        release_id = result.scalar_one_or_none()
        if release_id is not None:
            return release_id
        release_id = uuid.uuid4()
        await self._session.execute(
            insert(self._release_table).values(
                id=release_id,
                anime_id=anime_id,
                title=anime_row["title"],
                year=anime_row["year"],
                status=anime_row["status"],
            )
        )
        return release_id

    async def _get_release_id(self, anime_id: uuid.UUID) -> uuid.UUID | None:
        result = await self._session.execute(
            select(self._release_table.c.id)
            .where(self._release_table.c.anime_id == anime_id)
            .order_by(self._release_table.c.created_at.asc())
        )
        return result.scalar_one_or_none()

    async def _get_episode_external(
        self, anime_external_id: int, episode_number: int
    ) -> Mapping[str, object] | None:
        result = await self._session.execute(
            select(anime_episodes_external).where(
                anime_episodes_external.c.anime_id == anime_external_id,
                anime_episodes_external.c.episode_number == episode_number,
            )
        )
        return result.mappings().first()

    async def _get_translation_types(self, anime_external_id: int) -> dict[str, str | None]:
        result = await self._session.execute(
            select(
                anime_translations.c.translation_code,
                anime_translations.c.translation_name,
                anime_translations.c.type,
            ).where(anime_translations.c.anime_id == anime_external_id)
        )
        mapping: dict[str, str | None] = {}
        for row in result.mappings():
            translation_type = row["type"].lower() if row["type"] else None
            if row["translation_code"]:
                mapping[row["translation_code"].lower()] = translation_type
            if row["translation_name"]:
                mapping[row["translation_name"].lower()] = translation_type
        return mapping

    def _filter_translations(
        self,
        available: list[str] | None,
        type_map: Mapping[str, str | None],
        settings: ParserSettings,
    ) -> list[str] | None:
        translations = list(
            dict.fromkeys(
                str(item).strip()
                for item in (available or [])
                if item and str(item).strip()
            )
        )
        if not translations:
            return None
        allowed_types = {item.lower() for item in settings.allowed_translation_types}
        allowed_translations = {
            item.lower() for item in settings.allowed_translations if item
        }
        filtered: list[str] = []
        for translation in translations:
            lowered = translation.lower()
            translation_type = type_map.get(lowered)
            if (
                allowed_types
                and translation_type
                and translation_type.lower() not in allowed_types
            ):
                continue
            if allowed_translations and lowered not in allowed_translations:
                continue
            filtered.append(translation)
        filtered = _sort_by_priority(filtered, settings.preferred_translation_priority)
        return filtered or None

    def _filter_qualities(
        self, available: list[str] | None, settings: ParserSettings
    ) -> list[str] | None:
        qualities = list(
            dict.fromkeys(
                str(item).strip()
                for item in (available or [])
                if item and str(item).strip()
            )
        )
        if not qualities:
            return None
        if settings.allowed_qualities:
            allowed = {item.lower() for item in settings.allowed_qualities}
            qualities = [item for item in qualities if item.lower() in allowed]
        qualities = _sort_by_priority(qualities, settings.preferred_quality_priority)
        return qualities or None

    async def _get_settings(self) -> ParserSettings:
        result = await self._session.execute(select(parser_settings).limit(1))
        row = result.mappings().first()
        return _settings_from_row(row)

    async def _upsert_episode(
        self,
        release_id: uuid.UUID,
        episode_number: int,
        iframe_url: str | None,
        translations: list[str] | None,
        qualities: list[str] | None,
    ) -> tuple[uuid.UUID, bool]:
        result = await self._session.execute(
            select(self._episode_table.c.id).where(
                self._episode_table.c.release_id == release_id,
                self._episode_table.c.number == episode_number,
            )
        )
        episode_id = result.scalar_one_or_none()
        created = episode_id is None
        
        # COMPLIANCE: Parser MUST set source="parser" and updated_by=NULL
        compliance_fields = {
            "source": "parser",
            "updated_by": None,
        }
        
        if episode_id is None:
            episode_id = uuid.uuid4()
            await self._session.execute(
                insert(self._episode_table).values(
                    id=episode_id,
                    release_id=release_id,
                    number=episode_number,
                    iframe_url=iframe_url,
                    available_translations=translations,
                    available_qualities=qualities,
                    **compliance_fields,
                )
            )
            return episode_id, created
        await self._session.execute(
            update(self._episode_table)
            .where(self._episode_table.c.id == episode_id)
            .values(
                iframe_url=iframe_url,
                available_translations=translations,
                available_qualities=qualities,
                # COMPLIANCE: Always set these on update
                source="parser",
                updated_by=None,
            )
        )
        return episode_id, created
