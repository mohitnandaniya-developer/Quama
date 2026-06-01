"""Alembic environment configuration."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import get_settings
from app.db.base import Base
from app.models import broker_session, conversation, message, user_asset  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override the URL from the app settings so alembic always uses the same
# DATABASE_URL as the running application; no manual alembic.ini edits needed.
_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.database_url.replace("%", "%%"))

# asyncpg does not support the synchronous psycopg-style URL used by some
# offline tooling, so we swap the scheme for the offline (synchronous) runner
# to use psycopg2 (or the generic postgresql dialect) which alembic can use
# without an async event loop.  For online mode we keep asyncpg.
_sync_url = _settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)


def run_migrations_offline() -> None:
    """Run migrations in offline mode (generates SQL script, no live connection)."""
    context.configure(
        url=_sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations against the provided connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in online mode (connects to the live database)."""
    # Pass SSL for Supabase/managed PostgreSQL; ignored for SQLite.
    connect_args: dict = {}
    if _settings.database_url.startswith("postgresql"):
        connect_args["ssl"] = "require"

    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _settings.database_url

    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
