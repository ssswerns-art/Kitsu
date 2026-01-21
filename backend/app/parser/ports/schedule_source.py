from typing import Protocol, Sequence

from ..domain.entities import ScheduleItem


class ScheduleSourcePort(Protocol):
    async def fetch_schedule(self) -> Sequence[ScheduleItem]:
        ...
