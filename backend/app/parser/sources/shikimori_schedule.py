from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ..config import ParserSettings
from ..domain.entities import ScheduleItem
from ..ports.schedule_source import ScheduleSourcePort
from ._http import RateLimitedRequester


class ShikimoriScheduleSource(ScheduleSourcePort):
    def __init__(
        self,
        settings: ParserSettings,
        *,
        base_url: str = "https://shikimori.one/api",
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
    ) -> None:
        self._settings = settings
        self._requester = RateLimitedRequester(
            base_url=base_url,
            rate_limit_seconds=rate_limit_seconds,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    async def fetch_schedule(self) -> Sequence[ScheduleItem]:
        payload = await self._requester.get_json("calendar")
        if not isinstance(payload, list):
            return []
        items: list[ScheduleItem] = []
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            anime = entry.get("anime") if isinstance(entry.get("anime"), Mapping) else {}
            anime_id = anime.get("id") or entry.get("anime_id") or entry.get("id")
            if anime_id is None:
                continue
            source_url = _normalize_url(anime.get("url"))
            items.append(
                ScheduleItem(
                    anime_source_id=str(anime_id),
                    episode_number=_as_int(entry.get("episode")),
                    airs_at=_parse_datetime(entry.get("next_episode_at")),
                    source_url=source_url,
                )
            )
        return items


def _normalize_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value)
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://shikimori.one{url}"


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
