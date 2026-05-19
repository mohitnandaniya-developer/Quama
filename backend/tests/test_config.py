"""Application settings tests."""

from __future__ import annotations

from app.config import Settings

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