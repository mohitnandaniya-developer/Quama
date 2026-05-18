"""API-facing gateway for market subscriptions and SSE fanout."""

from __future__ import annotations

import json
from typing import Any

from app.core.cache_keys import (
    market_channel,
    market_command_channel,
    market_snapshot_key,
    market_subscription_key,
)
from app.core.exceptions import (
    BrokerSessionNotFoundError,
    MarketDataNotConfiguredError,
)
from app.services.broker_session_service import ANGEL_ONE_BROKER, BrokerSessionService
from app.services.market_data_bus import MarketDataBus


class MarketDataGatewayService:
    """Own the API control plane for the live market-data pipeline."""

    def __init__(
        self,
        *,
        market_data_bus: MarketDataBus,
        broker_session_service: BrokerSessionService,
        subscription_ttl_seconds: int,
    ) -> None:
        self.market_data_bus = market_data_bus
        self.broker_session_service = broker_session_service
        self.subscription_ttl_seconds = subscription_ttl_seconds

    async def register_subscriptions(
        self,
        *,
        user_id: str,
        mode: int,
        replace: bool,
        instruments: list[dict[str, int | str]],
    ) -> dict[str, Any]:
        """Persist desired subscriptions and notify the worker."""
        self._ensure_enabled()
        session = await self.broker_session_service.get_active_session(
            user_id=user_id,
            broker=ANGEL_ONE_BROKER,
        )
        if session is None or not session.feed_token:
            raise BrokerSessionNotFoundError(
                "Broker market-feed session not found. Please reconnect Angel One."
            )

        subscription_key = market_subscription_key(user_id=user_id)
        payload = {
            "user_id": user_id,
            "broker": ANGEL_ONE_BROKER,
            "mode": mode,
            "replace": replace,
            "instruments": instruments,
        }
        existing = await self.market_data_bus.get_json(key=subscription_key)
        if existing == payload:
            return {
                **payload,
                "subscription_key": subscription_key,
                "command_channel": market_command_channel(),
            }

        saved = await self.market_data_bus.set_json(
            key=subscription_key,
            payload=payload,
            ttl_seconds=self.subscription_ttl_seconds,
        )
        if not saved:
            raise MarketDataNotConfiguredError(
                "Unable to persist market subscription intent to Redis."
            )
        await self.market_data_bus.publish_json(
            channel=market_command_channel(),
            payload={"type": "subscription_update", **payload},
        )
        return {
            **payload,
            "subscription_key": subscription_key,
            "command_channel": market_command_channel(),
        }

    async def stream_payloads(
        self,
        *,
        instrument_tokens: list[str],
    ):
        """Yield JSON-encoded snapshots followed by live ticks for SSE."""
        self._ensure_enabled()
        for instrument_token in instrument_tokens:
            snapshot = await self.market_data_bus.get_json(
                key=market_snapshot_key(instrument_token=instrument_token)
            )
            if snapshot is not None:
                yield json.dumps(
                    {
                        "channel": market_channel(instrument_token=instrument_token),
                        "tick": snapshot,
                        "snapshot": True,
                    },
                    separators=(",", ":"),
                )

        channels = [
            market_channel(instrument_token=token) for token in instrument_tokens
        ]
        async for channel, payload in self.market_data_bus.iter_channel_messages(
            channels=channels
        ):
            yield json.dumps(
                {"channel": channel, "tick": payload, "snapshot": False},
                separators=(",", ":"),
            )

    def _ensure_enabled(self) -> None:
        if not self.market_data_bus.enabled:
            raise MarketDataNotConfiguredError(
                "MARKET_DATA_REDIS_URL or REDIS_URL is required for market streaming."
            )
