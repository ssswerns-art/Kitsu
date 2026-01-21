from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from ..config import ParserSettings
from ..domain.entities import AnimeExternal, AnimeRelationExternal
from ..ports.catalog_source import CatalogSourcePort
from ._http import RateLimitedRequester


class ShikimoriCatalogSource(CatalogSourcePort):
    def __init__(
        self,
        settings: ParserSettings,
        *,
        base_url: str = "https://shikimori.one/api",
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        page: int = 1,
        limit: int = 50,
    ) -> None:
        self._settings = settings
        self._page = page
        self._limit = limit
        self._requester = RateLimitedRequester(
            base_url=base_url,
            rate_limit_seconds=rate_limit_seconds,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    async def fetch_catalog(self) -> Sequence[AnimeExternal]:
        payload = await self._requester.get_json(
            "animes",
            params={
                "page": str(self._page),
                "limit": str(self._limit),
            },
        )
        if not isinstance(payload, list):
            return []
        return [
            self._map_anime(item)
            for item in payload
            if isinstance(item, Mapping) and item.get("id") is not None
        ]

    def _map_anime(self, item: Mapping[str, Any]) -> AnimeExternal:
        title_ru = _as_text(item.get("russian"))
        title_en = _first_text(item.get("english"))
        title_original = _first_text(item.get("japanese")) or _as_text(item.get("name"))
        title = title_ru or title_en or title_original or str(item.get("id"))
        description = _as_text(item.get("description")) or _as_text(
            item.get("description_html")
        )
        poster_url = _normalize_image(item.get("image"))
        season, year = _extract_season_year(item)
        genres = _extract_genres(item.get("genres"))
        relations = _extract_relations(item.get("relations") or item.get("related"))
        return AnimeExternal(
            source_id=str(item.get("id")),
            title=title,
            original_title=title_original,
            title_ru=title_ru,
            title_en=title_en,
            description=description,
            poster_url=poster_url,
            year=year,
            season=season,
            status=_as_text(item.get("status")),
            genres=genres,
            relations=relations,
        )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            text = _as_text(item)
            if text:
                return text
        return None
    return _as_text(value)


def _normalize_image(value: Any) -> str | None:
    if isinstance(value, Mapping):
        value = value.get("original") or value.get("preview")
    url = _as_text(value)
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://shikimori.one{url}"


def _extract_season_year(item: Mapping[str, Any]) -> tuple[str | None, int | None]:
    season_raw = _as_text(item.get("season"))
    year = None
    season = None
    if season_raw and "_" in season_raw:
        season, year_text = season_raw.split("_", maxsplit=1)
        try:
            year = int(year_text)
        except ValueError:
            year = None
    if year is None:
        year_value = item.get("year")
        if isinstance(year_value, int):
            year = year_value
        else:
            aired_on = _as_text(item.get("aired_on"))
            if aired_on:
                try:
                    year = datetime.fromisoformat(aired_on).year
                except ValueError:
                    year = None
    return season, year


def _extract_genres(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    genres = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        name = _as_text(item.get("russian") or item.get("name"))
        if name:
            genres.append(name)
    return genres


def _extract_relations(value: Any) -> list[AnimeRelationExternal]:
    if not isinstance(value, list):
        return []
    relations: list[AnimeRelationExternal] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        relation_type = _as_text(
            item.get("relation") or item.get("relation_kind") or item.get("relation_ru")
        )
        target = item.get("anime") or item.get("manga") or item
        if isinstance(target, Mapping):
            related_id = target.get("id")
        else:
            related_id = None
        if relation_type and related_id is not None:
            relations.append(
                AnimeRelationExternal(
                    relation_type=relation_type, related_source_id=str(related_id)
                )
            )
    return relations
