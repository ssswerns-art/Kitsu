from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..config import ParserSettings
from ..domain.entities import EpisodeExternal, TranslationExternal
from ..ports.episode_source import EpisodeSourcePort
from ._http import RateLimitedRequester


class KodikEpisodeSource(EpisodeSourcePort):
    def __init__(
        self,
        settings: ParserSettings,
        *,
        base_url: str = "https://kodikapi.com",
        rate_limit_seconds: float = 1.0,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        search_params: Mapping[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._search_params = dict(search_params or {})
        self._requester = RateLimitedRequester(
            base_url=base_url,
            rate_limit_seconds=rate_limit_seconds,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

    async def fetch_episodes(self) -> Sequence[EpisodeExternal]:
        return await self._fetch_episodes()

    async def fetch_episodes_for(
        self, search_params: Mapping[str, str] | None = None
    ) -> Sequence[EpisodeExternal]:
        return await self._fetch_episodes(search_params)

    async def _fetch_episodes(
        self, search_params: Mapping[str, str] | None = None
    ) -> list[EpisodeExternal]:
        params = {**self._search_params, **dict(search_params or {})}
        payload = await self._requester.get_json("search", params=params)
        if not isinstance(payload, Mapping):
            return []
        results = payload.get("results")
        if not isinstance(results, list):
            return []
        episodes: list[EpisodeExternal] = []
        for item in results:
            if isinstance(item, Mapping):
                episodes.extend(self._map_result(item))
        return episodes

    def _map_result(self, item: Mapping[str, Any]) -> list[EpisodeExternal]:
        anime_id = (
            item.get("shikimori_id")
            or item.get("anime_id")
            or item.get("id")
            or item.get("title_id")
        )
        if anime_id is None:
            return []
        translations = _extract_translations(item)
        filtered_translations = _filter_translations(translations, self._settings)
        if translations and not filtered_translations and _has_translation_filters(self._settings):
            return []
        qualities = _extract_qualities(item)
        filtered_qualities = _filter_qualities(qualities, self._settings)
        if qualities and not filtered_qualities and self._settings.allowed_qualities:
            return []
        episode_links = _extract_episode_links(item)
        if not episode_links:
            return []
        translation_name = (
            filtered_translations[0].name if filtered_translations else None
        )
        quality_name = filtered_qualities[0] if filtered_qualities else None
        return [
            EpisodeExternal(
                anime_source_id=str(anime_id),
                number=number,
                title=None,
                translation=translation_name,
                quality=quality_name,
                stream_url=url,
                translations=filtered_translations,
                qualities=filtered_qualities,
            )
            for number, url in episode_links.items()
        ]


def _extract_translations(item: Mapping[str, Any]) -> list[TranslationExternal]:
    translations: list[TranslationExternal] = []
    raw = item.get("translations")
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, Mapping):
                translations.append(_normalize_translation(entry))
    single = item.get("translation")
    if isinstance(single, Mapping):
        translations.append(_normalize_translation(single))
    seen: set[tuple[str, str, str | None]] = set()
    deduped: list[TranslationExternal] = []
    for translation in translations:
        if not (translation.code or translation.name):
            continue
        key = (translation.code, translation.name, translation.type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(translation)
    return deduped


def _normalize_translation(entry: Mapping[str, Any]) -> TranslationExternal:
    code_value = entry.get("id") or entry.get("code") or entry.get("uid")
    code = str(code_value) if code_value is not None else ""
    name_value = entry.get("title") or entry.get("name")
    name = str(name_value) if name_value is not None else code
    type_value = _normalize_translation_type(entry.get("type") or entry.get("kind"))
    return TranslationExternal(code=code, name=name, type=type_value)


def _normalize_translation_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).lower()
    if "sub" in text:
        return "sub"
    if "voice" in text or "dub" in text:
        return "voice"
    return None


def _extract_qualities(item: Mapping[str, Any]) -> list[str]:
    qualities: list[str] = []
    raw = item.get("qualities")
    if isinstance(raw, list):
        qualities.extend(_normalize_quality(entry) for entry in raw)
    quality = item.get("quality")
    normalized = _normalize_quality(quality)
    if normalized:
        qualities.append(normalized)
    return [quality for quality in qualities if quality]


def _normalize_quality(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return f"{text}p"
    return text


def _extract_episode_links(item: Mapping[str, Any]) -> dict[int, str]:
    episodes: dict[int, str] = {}
    raw_episodes = item.get("episodes")
    if isinstance(raw_episodes, Mapping):
        episodes.update(_normalize_episode_map(raw_episodes))
    raw_seasons = item.get("seasons")
    if isinstance(raw_seasons, Mapping):
        for season in raw_seasons.values():
            if isinstance(season, Mapping):
                season_eps = season.get("episodes")
                if isinstance(season_eps, Mapping):
                    episodes.update(_normalize_episode_map(season_eps))
    if not episodes:
        link = item.get("link")
        if link:
            number = _as_int(item.get("last_episode") or item.get("episodes_count"))
            if number is not None:
                episodes[number] = str(link)
    return episodes


def _normalize_episode_map(raw: Mapping[Any, Any]) -> dict[int, str]:
    normalized: dict[int, str] = {}
    for key, value in raw.items():
        number = _as_int(key)
        if number is None or value is None:
            continue
        normalized[number] = str(value)
    return normalized


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _filter_translations(
    translations: list[TranslationExternal], settings: ParserSettings
) -> list[TranslationExternal]:
    if not translations:
        return []
    allowed_types = {item.lower() for item in settings.allowed_translation_types}
    allowed_translations = {item.lower() for item in settings.allowed_translations}
    filtered: list[TranslationExternal] = []
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
        filtered.append(translation)
    return filtered


def _filter_qualities(qualities: list[str], settings: ParserSettings) -> list[str]:
    if not qualities:
        return []
    if not settings.allowed_qualities:
        return list(dict.fromkeys(qualities))
    allowed = {item.lower() for item in settings.allowed_qualities}
    return [quality for quality in qualities if quality.lower() in allowed]


def _has_translation_filters(settings: ParserSettings) -> bool:
    return bool(settings.allowed_translations or settings.allowed_translation_types)
