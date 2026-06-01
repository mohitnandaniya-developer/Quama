"""Live market-data pipeline schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketInstrument(BaseModel):
    """One instrument subscription target."""

    model_config = ConfigDict(extra="forbid")

    exchange_type: int = Field(ge=1)
    instrument_token: str = Field(min_length=1)


class MarketSubscriptionRequest(BaseModel):
    """Desired market subscriptions for one subscriber."""

    model_config = ConfigDict(extra="forbid")

    mode: int = Field(default=1, ge=1, le=4)
    replace: bool = True
    instruments: list[MarketInstrument]


class MarketSubscriptionResponse(BaseModel):
    """Acknowledgement returned after subscription registration."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    broker: str
    mode: int
    replace: bool
    instruments: list[MarketInstrument]
    subscription_key: str
    command_channel: str
