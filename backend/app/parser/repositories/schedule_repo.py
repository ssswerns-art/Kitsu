from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import ScheduleItem
from ..tables import anime_schedule

logger = logging.getLogger(__name__)


def _insert_for(session: AsyncSession):
    bind = session.get_bind()
    dialect = bind.dialect.name if bind is not None else "postgresql"
    if dialect == "sqlite":
        return sqlite_insert
    return pg_insert


class ScheduleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        source_id: int,
        items: Sequence[ScheduleItem],
        anime_id_map: Mapping[str, int],
        *,
        checked_at: datetime,
    ) -> tuple[int, int]:
        """
        Upsert schedule items with exactly-once semantics.
        
        IDEMPOTENCY KEY: (anime_id, source_id, episode_number)
        INVARIANT: Uses INSERT ... ON CONFLICT DO UPDATE for atomic idempotency.
        """
        if not items:
            return 0, 0
        rows = []
        for item in items:
            anime_id = anime_id_map.get(str(item.anime_source_id))
            if anime_id is None:
                continue
            rows.append(
                {
                    "anime_id": anime_id,
                    "source_id": source_id,
                    "episode_number": item.episode_number,
                    "air_datetime_utc": item.air_datetime,
                    "status": "scheduled" if item.air_datetime else None,
                    "source_hash": item.source_hash,
                    "last_checked_at": checked_at,
                }
            )
        skipped = len(items) - len(rows)
        if not rows:
            return 0, skipped
        insert_fn = _insert_for(self._session)
        stmt = insert_fn(anime_schedule).values(rows)
        # ATOMIC IDEMPOTENCY: ON CONFLICT ensures exactly-once effect
        stmt = stmt.on_conflict_do_update(
            index_elements=["anime_id", "source_id", "episode_number"],
            set_={
                "air_datetime_utc": stmt.excluded.air_datetime_utc,
                "status": stmt.excluded.status,
                "source_hash": stmt.excluded.source_hash,
                "last_checked_at": stmt.excluded.last_checked_at,
            },
        )
        await self._session.execute(stmt)
        logger.info(
            "operation=parser:schedule action=upsert source_id=%d count=%d",
            source_id,
            len(rows),
        )
        return len(rows), skipped
