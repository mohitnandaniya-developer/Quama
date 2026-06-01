"""Application settings management."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

load_dotenv(".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    # LLM providers — only set the key(s) you actually use.
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")

    # NewsAPI.ai MCP key (server-side only).
    newsapi_key: str = Field(default="", alias="NEWS_API_KEY")

    # Cache / Session — provide one of the Redis variants.
    # rediss:// URLs are used as a direct Redis connection (no REST token needed).
    upstash_redis_rest_url: str = Field(default="", alias="UPSTASH_REDIS_REST_URL")
    upstash_redis_rest_token: str = Field(default="", alias="UPSTASH_REDIS_REST_TOKEN")

    # Database.
    database_url: str = Field(default="", alias="DATABASE_URL")
    debug: bool = Field(default=False, alias="DEBUG")
    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        alias="ALLOWED_ORIGINS",
    )

    clerk_jwks_url: str = Field(default="", alias="CLERK_JWKS_URL")
    clerk_jwt_key: str = Field(default="", alias="CLERK_JWT_KEY")
    clerk_issuer: str = Field(default="", alias="CLERK_ISSUER")
    clerk_authorized_parties: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        alias="CLERK_AUTHORIZED_PARTIES",
    )
    clerk_jwks_cache_ttl_seconds: int = Field(
        default=300,
        alias="CLERK_JWKS_CACHE_TTL_SECONDS",
    )
    broker_token_secret: str = Field(default="", alias="BROKER_TOKEN_SECRET")
    default_broker: str = Field(default="angel_one", alias="DEFAULT_BROKER")
    broker_jwt_cache_ttl_seconds: int = Field(
        default=82_800,
        alias="BROKER_JWT_CACHE_TTL_SECONDS",
    )
    chat_history_cache_ttl_seconds: int = Field(
        default=3600,
        alias="CHAT_HISTORY_CACHE_TTL_SECONDS",
    )
    portfolio_cache_ttl_seconds: int = Field(
        default=60,
        alias="PORTFOLIO_CACHE_TTL_SECONDS",
    )
    market_snapshot_ttl_seconds: int = Field(
        default=30,
        alias="MARKET_SNAPSHOT_TTL_SECONDS",
    )
    market_subscription_ttl_seconds: int = Field(
        default=3600,
        alias="MARKET_SUBSCRIPTION_TTL_SECONDS",
    )
    mcp_connection_ttl_seconds: int = Field(
        default=2_592_000,
        alias="MCP_CONNECTION_TTL_SECONDS",
    )
    market_worker_poll_interval_seconds: int = Field(
        default=5,
        alias="MARKET_WORKER_POLL_INTERVAL_SECONDS",
    )
    angel_one_price_scale: float = Field(
        default=100.0,
        alias="ANGEL_ONE_PRICE_SCALE",
    )

    # Broker API keys
    angel_one_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ANGEL_ONE_API_KEY",
            "ANGEL_ONE_MARKET_API_KEY",
        ),
    )
    angel_one_secret_key: str = Field(
        default="",
        alias="ANGEL_ONE_SECRET_KEY",
    )
    groww_api_key: str = Field(
        default="",
        alias="GROWW_API_KEY",
    )
    groww_secret_key: str = Field(
        default="",
        alias="GROWW_SECRET_KEY",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: str | list[str]) -> list[str]:
        """Parse allowed origins from a comma-delimited string."""
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        """Normalize managed Postgres URLs for SQLAlchemy's async engine."""
        if not isinstance(value, str):
            return value

        database_url = value.strip()
        if database_url.startswith("postgres://"):
            database_url = database_url.replace(
                "postgres://",
                "postgresql+asyncpg://",
                1,
            )
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )

        if not database_url.startswith("postgresql+asyncpg://"):
            return database_url

        try:
            from sqlalchemy.engine.url import make_url

            parsed_url = make_url(database_url)
        except Exception as exc:
            msg = (
                "Invalid DATABASE_URL. Use a complete PostgreSQL URL "
                "such as postgresql://user:password@host:5432/database."
            )
            raise ValueError(msg) from exc

        if not parsed_url.host:
            msg = "DATABASE_URL must include a PostgreSQL hostname."
            raise ValueError(msg)

        if parsed_url.query and "sslmode" in parsed_url.query:
            new_query = dict(parsed_url.query)
            keys_to_remove = [k for k in new_query if k.lower() == "sslmode"]
            for k in keys_to_remove:
                del new_query[k]
            parsed_url = parsed_url.set(query=new_query)

        return parsed_url.render_as_string(hide_password=False)

    @field_validator("clerk_authorized_parties", mode="before")
    @classmethod
    def parse_clerk_authorized_parties(cls, value: str | list[str]) -> list[str]:
        """Parse allowed Clerk authorized parties from a comma-delimited string."""
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: bool | str) -> bool:
        """Parse debug values from booleans or deployment-style strings."""
        if isinstance(value, bool):
            return value

        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production"}:
            return False

        msg = "DEBUG must be a boolean-compatible value."
        raise ValueError(msg)

    @field_validator(
        "clerk_jwks_cache_ttl_seconds",
        "broker_jwt_cache_ttl_seconds",
        "chat_history_cache_ttl_seconds",
        "portfolio_cache_ttl_seconds",
        "market_snapshot_ttl_seconds",
        "market_subscription_ttl_seconds",
        "mcp_connection_ttl_seconds",
    )
    @classmethod
    def validate_positive_ttl(cls, value: int) -> int:
        """Validate cache TTL settings."""
        if value < 1:
            msg = "Cache TTL values must be greater than zero."
            raise ValueError(msg)
        return value

    @property
    def market_data_bus_url(self) -> str:
        """Return the direct-Redis URL used by the market-data pipeline.

        Falls back to UPSTASH_REDIS_REST_URL when it is a native Redis URL
        (redis:// or rediss://), which is the typical Render/Upstash setup.
        """
        if self.upstash_redis_rest_url.startswith(("redis://", "rediss://")):
            return self.upstash_redis_rest_url.strip()
        return ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
