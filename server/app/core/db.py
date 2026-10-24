"""Database access: the engine, sessions, and the base class for every table.

How it fits together:
- `Database` is created once when the app starts (see `lifespan` in main.py) and stored on `app.state.db`.
- Each request that needs the database declares `session: SessionDep`; it gets its own `AsyncSession`,
  closed automatically after the request.
- Services decide when to write: they call `await session.commit()` explicitly. Nothing is committed implicitly.
- Never keep a session open while waiting on an LLM call (backend-standards §7): open, write, commit, close.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

import anyio
from fastapi import Depends, Request
from sqlalchemy import DateTime, MetaData, func, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, so Alembic migrations can find and drop them later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Parent class of every table model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def created_at_column() -> Mapped[datetime]:
    """A `created_at` timestamp filled in by the database itself (so clock skew between servers can't matter)."""
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Database:
    """Owns the connection pool. One instance per running app."""

    def __init__(self, url: str, *, echo: bool = False):
        self.engine: AsyncEngine = create_async_engine(
            url,
            echo=echo,
            pool_pre_ping=True,  # quietly replace connections the database closed while idle
            pool_size=5,
            max_overflow=10,
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def is_reachable(self, timeout_s: float = 2.0) -> bool:
        """True if a trivial query succeeds within the timeout. Used by the readiness check."""
        try:
            async with asyncio.timeout(timeout_s):
                async with self.engine.connect() as connection:
                    await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self.engine.dispose()


async def release_connection(session: AsyncSession) -> None:
    """Finish the session's current transaction so its connection goes back to the pool.

    Call this before slow outside work (an LLM call): otherwise the connection sits idle in a transaction for
    the whole wait, and a few slow requests can exhaust the pool. Anything pending is committed first.
    The session stays usable; the next query simply starts a new transaction.
    """
    await session.commit()


def get_database(request: Request) -> Database:
    return request.app.state.db


async def get_session(database: Annotated[Database, Depends(get_database)]) -> AsyncIterator[AsyncSession]:
    session = database.sessions()
    try:
        yield session
    finally:
        # Shielded: if the client disconnects, closing must still finish, or the connection is torn down mid-way.
        with anyio.CancelScope(shield=True):
            await session.close()


# Use in route signatures: `async def handler(session: SessionDep): ...`
SessionDep = Annotated[AsyncSession, Depends(get_session)]
# The whole database, for work that needs its own short sessions (streaming, the cost ledger).
DatabaseDep = Annotated[Database, Depends(get_database)]
