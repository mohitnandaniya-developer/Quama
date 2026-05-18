"""Redis-backed helpers for market-data pub/sub and subscription registry."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis

from app.core.cache_keys import market_subscription_pattern

logger = logging.getLogger(__name__)


class MarketDataBus:
    """Direct-Redis bus for live market streams and control messages."""

    def __init__(
        self,
        *,
        redis_url: str,
        redis_client: Redis | None = None,
    ) -> None:
        self.redis_url = redis_url.strip()
        self._owns_client = redis_client is None
        self.redis_client = redis_client or (
            Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
            )
            if self.redis_url
            else None
        )

    @property
    def enabled(self) -> bool:
        """Return whether the bus has a usable Redis connection."""
        return bool(self.redis_url and self.redis_client is not None)

    async def ping(self) -> bool:
        """Return whether Redis is reachable."""
        if not self.enabled or self.redis_client is None:
            return False
        try:
            return bool(await self.redis_client.ping())
        except Exception:
            return False

    async def publish_json(self, *, channel: str, payload: dict[str, Any]) -> int:
        """Publish a JSON payload to a Redis pub/sub channel."""
        if not self.enabled or self.redis_client is None:
            return 0
        try:
            return int(await self.redis_client.publish(channel, json.dumps(payload)))
        except Exception:
            logger.warning(
                "Market publish failed for channel %s.",
                channel,
                exc_info=True,
            )
            return 0

    async def set_json(
        self,
        *,
        key: str,
        payload: dict[str, Any],
        ttl_seconds: int,
    ) -> bool:
        """Persist a JSON payload under one Redis key."""
        if not self.enabled or self.redis_client is None:
            return False
        if ttl_seconds < 1:
            logger.warning("Market set skipped for key %s with invalid TTL.", key)
            return False
        try:
            return bool(
                await self.redis_client.set(key, json.dumps(payload), ex=ttl_seconds)
            )
        except Exception:
            logger.warning("Market set failed for key %s.", key, exc_info=True)
            return False

    async def get_json(self, *, key: str) -> dict[str, Any] | None:
        """Return one stored JSON payload."""
        if not self.enabled or self.redis_client is None:
            return None
        try:
            value = await self.redis_client.get(key)
        except Exception:
            logger.warning("Market get failed for key %s.", key, exc_info=True)
            return None
        if not value:
            return None
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    async def delete(self, *, key: str) -> bool:
        """Delete one Redis key."""
        if not self.enabled or self.redis_client is None:
            return False
        try:
            return bool(await self.redis_client.delete(key))
        except Exception:
            logger.warning("Market delete failed for key %s.", key, exc_info=True)
            return False

    async def list_subscription_payloads(self) -> dict[str, dict[str, Any]]:
        """Return all registered user subscription payloads."""
        if not self.enabled or self.redis_client is None:
            return {}

        try:
            keys = [
                key
                async for key in self.redis_client.scan_iter(
                    match=market_subscription_pattern()
                )
            ]
        except Exception:
            logger.warning("Market subscription scan failed.", exc_info=True)
            return {}
        if not keys:
            return {}

        try:
            values = await self.redis_client.mget(keys)
        except Exception:
            logger.warning("Market subscription mget failed.", exc_info=True)
            return {}
        payloads: dict[str, dict[str, Any]] = {}
        for value in values:
            if not value:
                continue
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                continue
            if not isinstance(decoded, dict):
                continue
            user_id = str(decoded.get("user_id", "")).strip()
            if not user_id:
                continue
            payloads[user_id] = decoded
        return payloads

    async def iter_channel_messages(
        self,
        *,
        channels: list[str],
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield decoded JSON messages from subscribed Redis channels."""
        if not self.enabled or self.redis_client is None:
            return

        pubsub = self.redis_client.pubsub()
        try:
            await pubsub.subscribe(*channels)
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=5.0,
                )
                if not message:
                    await asyncio.sleep(0.1)
                    continue

                channel = str(message.get("channel", ""))
                data = message.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if not isinstance(payload, dict):
                    continue
                yield channel, payload
        except Exception:
            logger.warning("Market pubsub listener failed.", exc_info=True)
            return
        finally:
            try:
                await pubsub.unsubscribe(*channels)
            finally:
                await pubsub.aclose()

    async def close(self) -> None:
        """Close the owned Redis client."""
        if self._owns_client and self.redis_client is not None:
            await self.redis_client.aclose()
