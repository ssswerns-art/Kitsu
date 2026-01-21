from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import AsyncContextManager, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

from ..services.autoupdate_service import (
    ParserEpisodeAutoupdateService,
    resolve_update_interval_minutes,
)
from ..services.sync_service import get_parser_settings


DEFAULT_INTERVAL_MINUTES = 60


class ParserAutoupdateScheduler:
    def __init__(
        self,
        *,
        session_factory: Callable[
            [], AsyncContextManager[AsyncSession]
        ] = AsyncSessionLocal,
        service_factory: Callable[..., ParserEpisodeAutoupdateService] = (
            ParserEpisodeAutoupdateService
        ),
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def run_once(self, *, force: bool = False) -> dict[str, object]:
        async with self._session_factory() as session:
            settings = await get_parser_settings(session)
            interval = resolve_update_interval_minutes(settings)
            if not settings.enable_autoupdate and not force:
                return {"status": "disabled", "interval_minutes": interval}
            service = self._service_factory(session=session, settings=settings)
            summary = await service.run(force=True)
            summary["interval_minutes"] = interval
            return summary

    async def _loop(self) -> None:
        while True:
            result = await self.run_once()
            interval = int(result.get("interval_minutes") or DEFAULT_INTERVAL_MINUTES)
            await asyncio.sleep(interval * 60)


parser_autoupdate_scheduler = ParserAutoupdateScheduler()
