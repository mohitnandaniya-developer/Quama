"""Broker API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AngelOneConnectRequest(BaseModel):
    """Request payload for Angel One session creation."""

    model_config = ConfigDict(extra="forbid")

    client_code: str
    password: str
    totp: str


class GrowwConnectRequest(BaseModel):
    """Request payload for Groww TOTP token creation."""

    model_config = ConfigDict(extra="forbid")

    api_key: str
    totp: str


class BrokerConnectResponse(BaseModel):
    """Sanitized broker connection response."""

    model_config = ConfigDict(extra="forbid")

    broker: str
    client_code: str
    connected: bool
    connected_at: datetime


class BrokerDisconnectResponse(BaseModel):
    """Disconnect response payload."""

    model_config = ConfigDict(extra="forbid")

    disconnected: bool


class BrokerStatusItem(BaseModel):
    """Connected broker summary for status screens."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    broker: str
    client_code: str
    connected_at: datetime
    is_active: bool


class BrokerStatusResponse(BaseModel):
    """Status list response."""

    model_config = ConfigDict(extra="forbid")

    items: list[BrokerStatusItem]


class BrokerPortfolioSummary(BaseModel):
    """Normalized broker portfolio totals for UI display."""

    model_config = ConfigDict(extra="forbid")

    funds: float | None
    investment: float | None
    overall_gain: float | None


class BrokerPortfolioResponse(BaseModel):
    """Portfolio summary response."""

    model_config = ConfigDict(extra="forbid")

    holdings: list[dict[str, Any]]
    funds: dict[str, Any]
    summary: BrokerPortfolioSummary
    connected_broker: str
    performance_history: list[dict[str, Any]] = Field(default_factory=list)
