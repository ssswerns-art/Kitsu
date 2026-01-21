from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import EpisodeExternal, TranslationExternal
from ..tables import anime_episodes_external, anime_translations


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


def _episode_translations(episode: EpisodeExternal) -> list[TranslationExternal]:
    if episode.translations:
        return list(episode.translations)
    if episode.translation:
        return [TranslationExternal(code=episode.translation, name=episode.translation)]
    return []


class EpisodeExternalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        source_id: int,
        items: Sequence[EpisodeExternal],
        anime_id_map: Mapping[str, int],
        *,
        updated_at: datetime,
    ) -> tuple[int, int, int]:
        if not items:
            return 0, 0, 0
        episode_rows = []
        translation_rows = {}
        for item in items:
            anime_id = anime_id_map.get(str(item.anime_source_id))
            if anime_id is None:
                continue
            qualities = list(dict.fromkeys(item.qualities or []))
            if item.quality and item.quality not in qualities:
                qualities.append(item.quality)
            translations = [t.name for t in item.translations if t.name]
            if item.translation and item.translation not in translations:
                translations.append(item.translation)
            episode_rows.append(
                {
                    "anime_id": anime_id,
                    "source_id": source_id,
                    "episode_number": item.episode_number,
                    "iframe_url": item.stream_url,
                    "available_qualities": qualities or None,
                    "available_translations": translations or None,
                    "updated_at": updated_at,
                }
            )
            for translation in _episode_translations(item):
                code = translation.code or translation.name
                if not code:
                    continue
                translation_rows[(anime_id, code)] = {
                    "anime_id": anime_id,
                    "source_id": source_id,
                    "translation_code": code,
                    "translation_name": translation.name or code,
                    "type": translation.type,
                    "enabled": True,
                    "priority": 0,
                }
        skipped = len(items) - len(episode_rows)
        if episode_rows:
            insert_fn = _insert_for(self._session)
            stmt = insert_fn(anime_episodes_external).values(episode_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["anime_id", "source_id", "episode_number"],
                set_={
                    "iframe_url": stmt.excluded.iframe_url,
                    "available_qualities": stmt.excluded.available_qualities,
                    "available_translations": stmt.excluded.available_translations,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            await self._session.execute(stmt)
        if translation_rows:
            insert_fn = _insert_for(self._session)
            stmt = insert_fn(anime_translations).values(list(translation_rows.values()))
            stmt = stmt.on_conflict_do_update(
                index_elements=["anime_id", "source_id", "translation_code"],
                set_={
                    "translation_name": stmt.excluded.translation_name,
                    "type": stmt.excluded.type,
                    "enabled": stmt.excluded.enabled,
                    "priority": stmt.excluded.priority,
                },
            )
            await self._session.execute(stmt)
        return len(episode_rows), skipped, len(translation_rows)
