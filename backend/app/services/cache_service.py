"""Redis cache service backed by Upstash REST or Redis URLs."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class CacheService:
    """Async cache wrapper around Upstash REST or direct Redis URLs."""

    _disabled_warning_emitted = False

    def __init__(
        self,
        *,
        base_url: str,
        token: str = "",
        client: httpx.AsyncClient | None = None,
        redis_client: Redis | None = None,
    ) -> None:
        self.base_url = base_url.strip()
        self.token = token.strip()
        self.mode = self._resolve_mode(self.base_url)
        self._owns_http_client = False
        self._owns_redis_client = False
        self.http_client: httpx.AsyncClient | None = None
        self.redis_client: Redis | None = None

        if self.mode == "rest":
            self._owns_http_client = client is None
            self.http_client = client or httpx.AsyncClient(
                base_url=self.base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5.0,
            )
        elif self.mode == "redis":
            self._owns_redis_client = redis_client is None
            self.redis_client = redis_client or Redis.from_url(
                self.base_url,
                decode_responses=True,
                socket_timeout=5,
            )
        elif self.mode == "disabled" and not CacheService._disabled_warning_emitted:
            logger.warning("CacheService is disabled - no Redis URL configured.")
            CacheService._disabled_warning_emitted = True

    @property
    def enabled(self) -> bool:
        """Return whether cache calls can be attempted."""
        if self.mode == "redis":
            return bool(self.base_url)
        if self.mode == "rest":
            return bool(self.base_url and self.token)
        return False

    async def ping(self) -> bool:
        """Return whether the backing cache can be reached."""
        if not self.enabled:
            return False

        try:
            if self.mode == "redis":
                if self.redis_client is None:
                    return False
                return bool(await self.redis_client.ping())

            result = await self._request("GET", "/ping")
            if isinstance(result, str):
                return result.upper() == "PONG"
            return bool(result)
        except Exception:
            logger.warning("Redis PING failed.", exc_info=True)
            return False

    async def get(self, key: str) -> Any | None:
        """Fetch a cached value by key."""
        if not self.enabled:
            return None

        try:
            if self.mode == "redis":
                if self.redis_client is None:
                    return None
                result = await self.redis_client.get(key)
            else:
                result = await self._request("GET", f"/get/{self._encode(key)}")
        except Exception:
            logger.warning("Redis GET failed for key %s.", key, exc_info=True)
            return None

        if result is None:
            return None
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return result
        return result

    async def set(self, key: str, value: Any, ttl_seconds: int) -> bool:
        """Set a cache value with TTL."""
        if not self.enabled:
            return False
        if ttl_seconds < 1:
            logger.warning("Redis SET skipped for key %s with invalid TTL.", key)
            return False

        try:
            payload = json.dumps(value)
            if self.mode == "redis":
                if self.redis_client is None:
                    return False
                result = await self.redis_client.set(key, payload, ex=ttl_seconds)
            else:
                result = await self._request(
                    "POST",
                    f"/set/{self._encode(key)}",
                    content=payload,
                    params={"EX": ttl_seconds},
                )
        except Exception:
            logger.warning("Redis SET failed for key %s.", key, exc_info=True)
            return False
        return result == "OK" or result is True

    async def delete(self, key: str) -> bool:
        """Delete a cache key."""
        if not self.enabled:
            return False

        try:
            if self.mode == "redis":
                if self.redis_client is None:
                    return False
                result = await self.redis_client.delete(key)
            else:
                result = await self._request("GET", f"/del/{self._encode(key)}")
        except Exception:
            logger.warning("Redis DEL failed for key %s.", key, exc_info=True)
            return False
        return bool(result)

    async def exists(self, key: str) -> bool:
        """Return whether a cache key exists."""
        if not self.enabled:
            return False

        try:
            if self.mode == "redis":
                if self.redis_client is None:
                    return False
                result = await self.redis_client.exists(key)
            else:
                result = await self._request("GET", f"/exists/{self._encode(key)}")
        except Exception:
            logger.warning("Redis EXISTS failed for key %s.", key, exc_info=True)
            return False
        return bool(result)

    async def close(self) -> None:
        """Close any owned network client."""
        if self._owns_http_client and self.http_client is not None:
            await self.http_client.aclose()
        if self._owns_redis_client and self.redis_client is not None:
            await self.redis_client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        content: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a raw Upstash REST command."""
        if not self.enabled:
            msg = "Redis cache is not configured."
            raise RuntimeError(msg)
        if self.http_client is None:
            msg = "Redis REST client is not initialized."
            raise RuntimeError(msg)

        response = await self.http_client.request(
            method=method,
            url=path,
            content=content,
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result")

    @staticmethod
    def _encode(key: str) -> str:
        """URL-encode a Redis key for REST calls."""
        return quote(key, safe="")

    @staticmethod
    def _resolve_mode(base_url: str) -> str:
        """Resolve which cache backend mode should be used."""
        if base_url.startswith(("redis://", "rediss://")):
            return "redis"
        if base_url.startswith(("http://", "https://")):
            return "rest"
        return "disabled"
