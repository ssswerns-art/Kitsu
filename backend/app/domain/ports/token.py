from __future__ import annotations

from datetime import datetime
import uuid
from typing import Protocol


class RefreshTokenData(Protocol):
    user_id: uuid.UUID
    token_hash: str
    expires_at: datetime
    revoked: bool


class RefreshTokenPort(Protocol):
    async def create_or_rotate(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshTokenData:
        ...

    async def get_by_hash(
        self, token_hash: str, *, for_update: bool = False
    ) -> RefreshTokenData | None:
        ...

    async def get_by_user_id(
        self, user_id: uuid.UUID, *, for_update: bool = False
    ) -> RefreshTokenData | None:
        ...

    async def revoke(self, user_id: uuid.UUID) -> RefreshTokenData | None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
