"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, MissingUserIdError
from app.db.session import get_async_session
from app.services.asset_service import AssetService
from app.services.broker_session_service import (
    ANGEL_ONE_BROKER,
    GROWW_BROKER,
    BrokerSessionService,
)
from app.services.brokers.angel_one_service import AngelOneBrokerService
from app.services.brokers.groww_service import GrowwBrokerService
from app.services.brokers.registry import BrokerServiceRegistry
from app.services.cache_service import CacheService
from app.services.chat_service import ChatService
from app.services.clerk_auth_service import ClerkAuthService
from app.services.conversation_service import ConversationService
from app.services.market_data_bus import MarketDataBus
from app.services.market_data_gateway_service import MarketDataGatewayService
from app.services.mcp_agent_service import MCPAgentService
from app.services.mcp_connection_service import MCPConnectionService
from app.services.pinecone_service import PineconeService
from app.services.portfolio_sync_service import PortfolioSyncService


def get_settings_dependency(request: Request) -> Settings:
    """Return app settings from state or fallback to the cached global settings."""
    return getattr(request.app.state, "settings", get_settings())


async def get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yield an async database session."""
    async for session in get_async_session():
        yield session


def get_cache_service(request: Request) -> CacheService:
    """Return the application cache service."""
    cache_service = getattr(request.app.state, "cache_service", None)
    if cache_service is None:
        msg = (
            "Cache service is not initialized. "
            "Check that upstash_redis_rest_url and upstash_redis_rest_token are set."
        )
        raise RuntimeError(msg)
    return cache_service


def get_pinecone_service(request: Request) -> PineconeService:
    """Return the shared Pinecone service."""
    pinecone_service = getattr(request.app.state, "pinecone_service", None)
    if pinecone_service is None:
        msg = "Pinecone service is not initialized."
        raise RuntimeError(msg)
    return pinecone_service


def get_market_data_bus(request: Request) -> MarketDataBus:
    """Return the shared direct-Redis market data bus."""
    market_data_bus = getattr(request.app.state, "market_data_bus", None)
    if market_data_bus is None:
        msg = (
            "Market data bus is not initialized. "
            "Check that market_data_bus_url is configured correctly."
        )
        raise RuntimeError(msg)
    return market_data_bus


def get_clerk_auth_service(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ClerkAuthService:
    """Build the Clerk token verifier for the current request."""
    return ClerkAuthService(settings=settings)


async def require_user_id(
    clerk_auth_service: Annotated[ClerkAuthService, Depends(get_clerk_auth_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
) -> str:
    """Resolve the authenticated user id for protected endpoints."""
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return await clerk_auth_service.verify_token(token.strip())
        raise AuthenticationError("Invalid Authorization header.")

    if settings.debug:
        if not x_user_id or not x_user_id.strip():
            raise MissingUserIdError()
        return x_user_id.strip()

    raise AuthenticationError()


def get_conversation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
) -> ConversationService:
    """Build a conversation service for the current request."""
    return ConversationService(
        session=session,
        cache_service=cache_service,
    )


def get_chat_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    pinecone_service: Annotated[PineconeService, Depends(get_pinecone_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> ChatService:
    """Build a chat service for the current request."""
    broker_session_service = BrokerSessionService(
        session=session,
        cache_service=cache_service,
        settings=settings,
    )
    return ChatService(
        session=session,
        cache_service=cache_service,
        pinecone_service=pinecone_service,
        history_cache_ttl_seconds=settings.chat_history_cache_ttl_seconds,
        settings=settings,
        portfolio_sync_service=PortfolioSyncService(
            session=session,
            cache_service=cache_service,
            settings=settings,
            broker_session_service=broker_session_service,
        ),
        groww_broker_service=GrowwBrokerService(
            broker_session_service=broker_session_service,
        ),
    )


def get_asset_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    pinecone_service: Annotated[PineconeService, Depends(get_pinecone_service)],
) -> AssetService:
    """Build an asset service for the current request."""
    return AssetService(
        session=session,
        pinecone_service=pinecone_service,
    )


def get_broker_session_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> BrokerSessionService:
    """Build a broker session service for the current request."""
    return BrokerSessionService(
        session=session,
        cache_service=cache_service,
        settings=settings,
    )


def get_portfolio_sync_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> PortfolioSyncService:
    """Build a portfolio sync service for the current request."""
    broker_session_service = BrokerSessionService(
        session=session,
        cache_service=cache_service,
        settings=settings,
    )
    return PortfolioSyncService(
        session=session,
        cache_service=cache_service,
        settings=settings,
        broker_session_service=broker_session_service,
    )


def get_market_data_gateway_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    market_data_bus: Annotated[MarketDataBus, Depends(get_market_data_bus)],
) -> MarketDataGatewayService:
    """Build a market data gateway service for the current request."""
    broker_session_service = BrokerSessionService(
        session=session,
        cache_service=cache_service,
        settings=settings,
    )
    return MarketDataGatewayService(
        market_data_bus=market_data_bus,
        broker_session_service=broker_session_service,
        subscription_ttl_seconds=settings.market_subscription_ttl_seconds,
    )


def get_broker_registry(
    settings: Annotated[Settings, Depends(get_settings_dependency)],
    broker_session_service: Annotated[
        BrokerSessionService,
        Depends(get_broker_session_service),
    ],
    portfolio_sync_service: Annotated[
        PortfolioSyncService,
        Depends(get_portfolio_sync_service),
    ],
) -> BrokerServiceRegistry:
    """Build the broker registry with the currently installed adapters."""
    return BrokerServiceRegistry(
        services={
            ANGEL_ONE_BROKER: AngelOneBrokerService(
                broker_session_service=broker_session_service,
                portfolio_sync_service=portfolio_sync_service,
            ),
            GROWW_BROKER: GrowwBrokerService(
                broker_session_service=broker_session_service,
            ),
        },
        default_broker=settings.default_broker,
    )


def get_mcp_connection_service(
    cache_service: Annotated[CacheService, Depends(get_cache_service)],
    settings: Annotated[Settings, Depends(get_settings_dependency)],
) -> MCPConnectionService:
    """Build the user-scoped MCP connection registry service."""
    return MCPConnectionService(
        cache_service=cache_service,
        settings=settings,
        connection_ttl_seconds=settings.mcp_connection_ttl_seconds,
    )


def get_mcp_agent_service(
    connection_service: Annotated[
        MCPConnectionService,
        Depends(get_mcp_connection_service),
    ],
) -> MCPAgentService:
    """Build the MCP-aware agent controller service."""
    return MCPAgentService(connection_service=connection_service)
