"""Shared test fixtures for the backend test suite."""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["OPENAI_API_KEY"] = "openai-test-key"
os.environ["GOOGLE_API_KEY"] = "google-test-key"
os.environ["GROQ_API_KEY"] = "groq-test-key"
os.environ["UPSTASH_REDIS_REST_URL"] = "https://example.upstash.io"
os.environ["UPSTASH_REDIS_REST_TOKEN"] = "token"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test-bootstrap.db"
os.environ["DEBUG"] = "true"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
os.environ["ANGEL_ONE_API_KEY"] = "angel-api-key"
os.environ["ANGEL_ONE_MARKET_API_KEY"] = "angel-api-key"
os.environ["ANGEL_ONE_SECRET_KEY"] = "angel-secret"
os.environ["BROKER_TOKEN_SECRET"] = "LRhNFbp-P9fl0Pe4KfYz7PH3b3Ymz5lmp5F3N95R5X0="

from app.config import Settings, get_settings  # noqa: E402
from app.dependencies import get_cache_service  # noqa: E402
from app.main import create_app  # noqa: E402


class FakeCacheService:
    """In-memory cache substitute for tests."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.ttl_by_key: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: object, ttl_seconds: int) -> bool:
        self.store[key] = value
        self.ttl_by_key[key] = ttl_seconds
        return True

    async def delete(self, key: str) -> bool:
        self.ttl_by_key.pop(key, None)
        return self.store.pop(key, None) is not None

    async def ping(self) -> bool:
        return True


class FakeMarketDataBus:
    """In-memory direct-Redis substitute for market bus tests."""

    def __init__(self) -> None:
        self.enabled = True
        self.json_store: dict[str, dict[str, object]] = {}
        self.published: list[tuple[str, dict[str, object]]] = []

    async def ping(self) -> bool:
        return True

    async def publish_json(self, *, channel: str, payload: dict[str, object]) -> int:
        self.published.append((channel, payload))
        return 1

    async def set_json(
        self,
        *,
        key: str,
        payload: dict[str, object],
        ttl_seconds: int,
    ) -> bool:
        self.json_store[key] = {**payload, "_ttl_seconds": ttl_seconds}
        return True

    async def get_json(self, *, key: str) -> dict[str, object] | None:
        value = self.json_store.get(key)
        if value is None:
            return None
        return {k: v for k, v in value.items() if k != "_ttl_seconds"}

    async def delete(self, *, key: str) -> bool:
        return self.json_store.pop(key, None) is not None

    async def list_subscription_payloads(self) -> dict[str, dict[str, object]]:
        results: dict[str, dict[str, object]] = {}
        for value in self.json_store.values():
            user_id = str(value.get("user_id", "")).strip()
            if not user_id:
                continue
            results[user_id] = {k: v for k, v in value.items() if k != "_ttl_seconds"}
        return results

    async def iter_channel_messages(self, *, channels: list[str]):
        del channels
        if False:
            yield "", {}

    async def close(self) -> None:
        return None


@pytest.fixture
def test_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Provide isolated settings for tests."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://example.upstash.io")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "token")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("ANGEL_ONE_API_KEY", "angel-api-key")
    monkeypatch.setenv("ANGEL_ONE_MARKET_API_KEY", "angel-api-key")
    monkeypatch.setenv("ANGEL_ONE_SECRET_KEY", "angel-secret")
    monkeypatch.setenv(
        "BROKER_TOKEN_SECRET",
        "LRhNFbp-P9fl0Pe4KfYz7PH3b3Ymz5lmp5F3N95R5X0=",
    )
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def fake_cache_service() -> FakeCacheService:
    """Return a shared in-memory cache for the test app lifespan."""
    return FakeCacheService()


@pytest.fixture
def fake_market_data_bus() -> FakeMarketDataBus:
    """Return an in-memory market bus for tests."""
    return FakeMarketDataBus()


@pytest.fixture
async def client(
    test_settings: Settings,
    fake_cache_service: FakeCacheService,
    fake_market_data_bus: FakeMarketDataBus,
) -> AsyncIterator[AsyncClient]:
    """Yield an async test client with lifespan enabled."""
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_cache_service] = lambda: fake_cache_service

    async with LifespanManager(app):
        app.state.market_data_bus = fake_market_data_bus
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            yield async_client


@pytest.fixture
def user_headers() -> dict[str, str]:
    """Return default authenticated headers for tests."""
    return {"X-User-Id": "test-user"}
