from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session


class AsyncSessionAdapter:
    def __init__(self, session: Session, engine: sa.Engine) -> None:
        self._session = session
        self._engine = engine

    def get_bind(self) -> sa.Engine:
        return self._engine

    async def execute(self, *args, **kwargs):
        return self._session.execute(*args, **kwargs)

    async def commit(self) -> None:
        self._session.commit()

    async def rollback(self) -> None:
        self._session.rollback()
    
    def add(self, instance) -> None:
        """Add an instance to the session."""
        self._session.add(instance)
    
    async def refresh(self, instance, **kwargs) -> None:
        """Refresh an instance from the database."""
        self._session.refresh(instance, **kwargs)

    @asynccontextmanager
    async def begin(self):
        with self._session.begin():
            yield self
