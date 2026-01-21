from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import AnimeExternal
from ..tables import anime_external


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


def _hash_anime(anime: AnimeExternal) -> str:
    payload = {
        "title": anime.title,
        "original_title": anime.original_title,
        "title_ru": anime.title_ru,
        "title_en": anime.title_en,
        "description": anime.description,
        "poster_url": anime.poster_url,
        "year": anime.year,
        "season": anime.season,
        "status": anime.status,
        "genres": anime.genres,
        "relations": [
            {"type": relation.relation_type, "id": relation.related_source_id}
            for relation in anime.relations
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AnimeExternalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self, source_id: int, items: Sequence[AnimeExternal], *, seen_at: datetime
    ) -> dict[str, int]:
        if not items:
            return {}
        rows = [
            {
                "source_id": source_id,
                "external_id": str(item.source_id),
                "title_raw": item.title,
                "title_ru": item.title_ru,
                "title_en": item.title_en,
                "title_original": item.title_original,
                "description": item.description,
                "poster_url": item.poster_url,
                "year": item.year,
                "season": item.season,
                "status": item.status,
                "genres": list(item.genres) if item.genres else None,
                "match_confidence": None,
                "matched_by": "auto",
                "last_seen_at": seen_at,
                "source_hash": _hash_anime(item),
            }
            for item in items
        ]
        insert_fn = _insert_for(self._session)
        stmt = insert_fn(anime_external).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_id", "external_id"],
            set_={
                "title_raw": stmt.excluded.title_raw,
                "title_ru": stmt.excluded.title_ru,
                "title_en": stmt.excluded.title_en,
                "title_original": stmt.excluded.title_original,
                "description": stmt.excluded.description,
                "poster_url": stmt.excluded.poster_url,
                "year": stmt.excluded.year,
                "season": stmt.excluded.season,
                "status": stmt.excluded.status,
                "genres": stmt.excluded.genres,
                "match_confidence": stmt.excluded.match_confidence,
                "matched_by": stmt.excluded.matched_by,
                "last_seen_at": stmt.excluded.last_seen_at,
                "source_hash": stmt.excluded.source_hash,
            },
        )
        await self._session.execute(stmt)
        external_ids = [str(item.source_id) for item in items]
        result = await self._session.execute(
            select(anime_external.c.id, anime_external.c.external_id).where(
                anime_external.c.source_id == source_id,
                anime_external.c.external_id.in_(external_ids),
            )
        )
        return {row.external_id: row.id for row in result}
