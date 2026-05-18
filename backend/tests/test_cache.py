"""Cache service fallback behavior tests."""

from __future__ import annotations

import pytest

from app.services.cache_service import CacheService


@pytest.mark.asyncio
async def test_cache_service_disabled_mode_falls_back_cleanly() -> None:
    """Disabled Redis config should behave as a cache miss, not an exception."""
    cache = CacheService(base_url="", token="")

    assert cache.enabled is False
    assert await cache.ping() is False
    assert await cache.get("missing") is None
    assert await cache.set("key", {"value": 1}, 60) is False
    assert await cache.exists("key") is False
    assert await cache.delete("key") is False


@pytest.mark.asyncio
async def test_cache_service_rejects_invalid_ttl() -> None:
    """Invalid TTLs should not reach Redis clients."""

    class FakeRedis:
        def __init__(self) -> None:
            self.set_calls = 0

        async def set(self, *args, **kwargs):
            self.set_calls += 1
            return True

    redis = FakeRedis()
    cache = CacheService(
        base_url="redis://localhost:6379",
        redis_client=redis,  # type: ignore[arg-type]
    )

    assert await cache.set("key", "value", 0) is False
    assert redis.set_calls == 0
