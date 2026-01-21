from typing import Protocol, Sequence

from ..domain.entities import AnimeExternal


class CatalogSourcePort(Protocol):
    async def fetch_catalog(self) -> Sequence[AnimeExternal]:
        ...
