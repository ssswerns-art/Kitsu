from typing import Protocol, Sequence

from ..domain.entities import EpisodeExternal


class EpisodeSourcePort(Protocol):
    async def fetch_episodes(self) -> Sequence[EpisodeExternal]:
        ...
