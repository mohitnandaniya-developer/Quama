"""Portfolio sync pipeline schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class PortfolioSyncRequest(BaseModel):
    """Request payload for a portfolio sync."""

    model_config = ConfigDict(extra="forbid")

    force_refresh: bool = False
    trigger: Literal["user_action", "schedule", "agent_request"] = "user_action"


class PortfolioSummary(BaseModel):
    """Normalized portfolio totals for UI and AI agent use."""

    model_config = ConfigDict(extra="forbid")

    funds: float | None
    investment: float | None
    holdings_market_value: float | None
    positions_market_value: float | None
    overall_gain: float | None


class PortfolioSnapshotResponse(BaseModel):
    """Portfolio snapshot response shared by UI and AI agents."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    broker: str
    trigger: str
    synced_at: datetime
    cache_ttl_seconds: int
    holdings: list[dict[str, Any]]
    positions: list[dict[str, Any]]
    order_history: list[dict[str, Any]]
    funds: dict[str, Any]
    performance_history: list[dict[str, Any]]
    summary: PortfolioSummary
