"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.agent_router import router as agent_router
from app.api.v1.assets_router import router as assets_router
from app.api.v1.broker_router import router as brokers_router
from app.api.v1.chat_router import router as chat_router
from app.api.v1.conversations_router import router as conversations_router
from app.api.v1.market_router import router as market_router
from app.api.v1.mcp_router import router as mcp_router
from app.api.v1.models_router import router as models_router
from app.api.v1.portfolio_router import router as portfolio_router

router = APIRouter()
router.include_router(models_router, prefix="/models", tags=["models"])
router.include_router(assets_router, prefix="/assets", tags=["assets"])
router.include_router(brokers_router, prefix="/brokers", tags=["brokers"])
router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
router.include_router(market_router, prefix="/market", tags=["market"])
router.include_router(mcp_router, prefix="/mcp", tags=["mcp"])
router.include_router(agent_router, prefix="/agent", tags=["agent"])
router.include_router(
    conversations_router,
    prefix="/conversations",
    tags=["conversations"],
)
router.include_router(chat_router, prefix="/chat", tags=["chat"])
