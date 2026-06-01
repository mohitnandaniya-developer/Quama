"""Application settings tests."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager

from app.config import Settings
from app.db.session import _build_engine_kwargs
from app.main import create_app, run_migrations


def test_database_url_normalizes_render_postgres_urls() -> None:
    """Render-style Postgres URLs should use the async SQLAlchemy driver."""
    settings = Settings(
        DATABASE_URL="postgresql://user:password@host:5432/quama",
        UPSTASH_REDIS_REST_URL="",
        BROKER_TOKEN_SECRET="LRhNFbp-P9fl0Pe4KfYz7PH3b3Ymz5lmp5F3N95R5X0=",
    )

    assert settings.database_url == "postgresql+asyncpg://user:password@host:5432/quama"


def test_database_url_normalizes_legacy_postgres_scheme() -> None:
    """postgres:// aliases should be accepted for managed Postgres providers."""
    settings = Settings(
        DATABASE_URL="postgres://user:password@host:5432/quama",
        UPSTASH_REDIS_REST_URL="",
        BROKER_TOKEN_SECRET="LRhNFbp-P9fl0Pe4KfYz7PH3b3Ymz5lmp5F3N95R5X0=",
    )

    assert settings.database_url == "postgresql+asyncpg://user:password@host:5432/quama"


def test_database_url_removes_asyncpg_unsupported_sslmode_query() -> None:
    """SSL is configured with connect_args, not asyncpg URL query parameters."""
    settings = Settings(
        DATABASE_URL="postgresql://user:password@host:5432/quama?sslmode=require",
        UPSTASH_REDIS_REST_URL="",
        BROKER_TOKEN_SECRET="LRhNFbp-P9fl0Pe4KfYz7PH3b3Ymz5lmp5F3N95R5X0=",
    )

    assert settings.database_url == "postgresql+asyncpg://user:password@host:5432/quama"


def test_database_url_rejects_invalid_port() -> None:
    """Malformed Postgres URLs should fail with an actionable validation error."""
    with pytest.raises(
        ValueError,
        match="DATABASE_URL has an invalid port",
    ) as exc_info:
        Settings(
            DATABASE_URL="postgresql://host:not-a-port",
            UPSTASH_REDIS_REST_URL="",
        )

    assert "not-a-port" not in str(exc_info.value)


def test_run_migrations_accepts_percent_encoded_password(monkeypatch) -> None:
    """Alembic config interpolation should not reject encoded URL characters."""
    database_url = "postgresql+asyncpg://user:p%23ssword@host:5432/quama"
    captured_url = ""

    def fake_upgrade(alembic_config, revision: str) -> None:
        nonlocal captured_url
        assert revision == "head"
        captured_url = alembic_config.get_main_option("sqlalchemy.url")

    monkeypatch.setattr("app.main.command.upgrade", fake_upgrade)

    run_migrations(database_url)

    assert captured_url == database_url


def test_database_engine_options_are_postgres_specific() -> None:
    """Pooling and SSL options should not leak into SQLite engines."""
    assert _build_engine_kwargs("sqlite+aiosqlite:///test.db") == {"future": True}
    assert _build_engine_kwargs("postgresql+asyncpg://host/quama") == {
        "future": True,
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "connect_args": {"ssl": "require", "timeout": 10},
    }


@pytest.mark.asyncio
async def test_app_lifespan_allows_missing_database_url() -> None:
    """The API should start in degraded mode when database setup is omitted."""
    app = create_app(
        settings=Settings(
            DATABASE_URL="",
            UPSTASH_REDIS_REST_URL="",
        )
    )

    async with LifespanManager(app):
        assert app.state.settings.database_url == ""
