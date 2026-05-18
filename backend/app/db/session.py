"""Async database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _build_engine_kwargs(database_url: str) -> dict:
    """Return engine kwargs appropriate for the dialect."""
    kwargs: dict = {"future": True}
    if database_url.startswith("postgresql"):
        # Supabase (and most managed PG) requires SSL. asyncpg accepts "require"
        # as the ssl parameter inside connect_args.
        kwargs["connect_args"] = {"ssl": "require"}
    return kwargs


def init_engine(database_url: str, *, echo: bool = False) -> None:
    """Initialize the global async engine and session factory."""
    global _engine, _session_maker

    if _engine is None:
        engine_kwargs = _build_engine_kwargs(database_url)
        _engine = create_async_engine(database_url, echo=echo, **engine_kwargs)
        _session_maker = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )


def get_engine() -> AsyncEngine:
    """Return the initialized async engine."""
    if _engine is None:
        msg = "Database engine has not been initialized."
        raise RuntimeError(msg)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return the initialized async session factory."""
    if _session_maker is None:
        msg = "Session factory has not been initialized."
        raise RuntimeError(msg)
    return _session_maker


async def get_async_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async database session."""
    if _session_maker is None:
        yield None
        return
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def dispose_engine() -> None:
    """Dispose the async engine if it exists."""
    global _engine, _session_maker

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None
