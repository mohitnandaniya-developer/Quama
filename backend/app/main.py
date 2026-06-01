"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from alembic.config import Config as AlembicConfig
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app import __version__
from app.api.v1.router import router as api_v1_router
from app.config import Settings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import dispose_engine, get_session_maker, init_engine
from app.dependencies import get_cache_service, get_db_session
from app.services.broker_session_service import refresh_all_expiring_tokens
from app.services.cache_service import CacheService
from app.services.market_data_bus import MarketDataBus

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_migrations(database_url: str) -> None:
    """Run Alembic migrations to the latest revision."""
    alembic_config = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(resolved_settings)
        logger.info("Starting Quama backend version %s.", __version__)
        if resolved_settings.database_url:
            await asyncio.to_thread(run_migrations, resolved_settings.database_url)
            init_engine(resolved_settings.database_url, echo=resolved_settings.debug)
        else:
            logger.warning("DATABASE_URL is not set. Skipping database initialization.")

        cache_service = CacheService(
            base_url=resolved_settings.upstash_redis_rest_url,
            token=resolved_settings.upstash_redis_rest_token,
        )
        market_data_bus = MarketDataBus(redis_url=resolved_settings.market_data_bus_url)

        app.state.settings = resolved_settings
        app.state.cache_service = cache_service
        app.state.market_data_bus = market_data_bus
        session_maker = get_session_maker() if resolved_settings.database_url else None

        async def token_refresh_loop() -> None:
            if session_maker is None:
                logger.warning("Token refresh loop disabled: DATABASE_URL is missing.")
                return
            while True:
                await asyncio.sleep(1800)
                try:
                    async with session_maker() as session:
                        await refresh_all_expiring_tokens(
                            session,
                            cache_service,
                            resolved_settings,
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning(
                        "Broker token refresh loop failed (will retry in 30min): %s",
                        exc,
                        exc_info=False,
                    )

        refresh_task = asyncio.create_task(token_refresh_loop())

        try:
            yield
        finally:
            logger.info("Shutting down Quama backend.")
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                logger.debug("Broker token refresh loop stopped.")
            await cache_service.close()
            await market_data_bus.close()
            await dispose_engine()
            logger.info("Quama backend shutdown complete.")

    app = FastAPI(
        title="AI Chat Backend",
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check(
        session: Annotated[AsyncSession | None, Depends(get_db_session)],
        cache_service: Annotated[CacheService, Depends(get_cache_service)],
    ) -> dict[str, Any]:
        """Return application health status."""
        db_status = "ok"
        redis_status = "ok"

        try:
            if session:
                await session.execute(text("SELECT 1"))
            else:
                db_status = "disabled"
        except Exception as exc:
            logger.warning("Database health check failed: %s", exc, exc_info=False)
            db_status = "error"

        if not await cache_service.ping():
            redis_status = "degraded"

        overall_status = (
            "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
        )
        return {
            "status": overall_status,
            "db": db_status,
            "redis": redis_status,
            "version": __version__,
        }

    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
