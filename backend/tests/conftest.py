"""Pytest fixtures for backend tests."""

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
os.environ["PINECONE_API_KEY"] = "pinecone-test-key"
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

    async def exists(self, key: str) -> bool:
        return key in self.store

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


class FakePineconeService:
    """In-memory Pinecone substitute for asset RAG and memory tests."""

    def __init__(self) -> None:
        self.enabled = True
        self.asset_records: dict[str, list[dict[str, object]]] = {}
        self.memory_records: dict[str, list[dict[str, object]]] = {}

    async def close(self) -> None:
        return None

    def build_user_namespace(self, *, user_id: str) -> str:
        return f"user-{user_id}"

    def build_memory_namespace(self, *, user_id: str) -> str:
        return f"memory-{user_id}"

    async def chunk_and_index(
        self,
        *,
        asset_id: str,
        user_id: str,
        file_path: str,
        file_name: str,
        mime_type: str,
    ) -> dict[str, int]:
        namespace = self.build_user_namespace(user_id=user_id)
        path = Path(file_path)
        if mime_type.startswith("image/"):
            text = f"Image asset: {file_name}"
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")
        self.asset_records.setdefault(namespace, []).append(
            {
                "asset_id": asset_id,
                "user_id": user_id,
                "asset_name": file_name,
                "text": text or f"Stored asset: {file_name}",
                "mime_type": mime_type,
            }
        )
        return {"chunks_created": 1, "vectors_upserted": 1}

    async def delete_asset_vectors(self, *, asset_id: str, user_id: str) -> None:
        namespace = self.build_user_namespace(user_id=user_id)
        self.asset_records[namespace] = [
            record
            for record in self.asset_records.get(namespace, [])
            if record["asset_id"] != asset_id
        ]

    async def retrieve_context(
        self,
        *,
        user_message: str,
        user_id: str,
        top_k: int = 5,
        relevance_threshold: float = 0.75,
    ) -> list[str]:
        del relevance_threshold
        namespace = self.build_user_namespace(user_id=user_id)
        query_terms = {
            term.lower() for term in user_message.split() if len(term.strip()) > 2
        }
        scored: list[tuple[int, str]] = []
        for record in self.asset_records.get(namespace, []):
            text = str(record["text"])
            overlap = sum(term in text.lower() for term in query_terms)
            if overlap <= 0:
                continue
            scored.append((overlap, f"{text} (source: {record['asset_name']})"))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [result for _, result in scored[:top_k]]

    async def store_memory_summary(
        self,
        *,
        user_id: str,
        conversation_id: str,
        summary: str,
        segment_key: str,
    ) -> bool:
        namespace = self.build_memory_namespace(user_id=user_id)
        self.memory_records.setdefault(namespace, []).append(
            {
                "id": f"{conversation_id}:{segment_key}",
                "summary": summary,
            }
        )
        return True

    async def retrieve_memories(
        self,
        *,
        user_id: str,
        user_message: str,
        top_k: int = 3,
        relevance_threshold: float = 0.75,
    ) -> list[str]:
        del relevance_threshold
        namespace = self.build_memory_namespace(user_id=user_id)
        query_terms = {
            term.lower() for term in user_message.split() if len(term.strip()) > 2
        }
        scored: list[tuple[int, str]] = []
        for record in self.memory_records.get(namespace, []):
            summary = str(record["summary"])
            overlap = sum(term in summary.lower() for term in query_terms)
            if overlap <= 0:
                continue
            scored.append((overlap, summary))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [summary for _, summary in scored[:top_k]]


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
    monkeypatch.setenv("PINECONE_API_KEY", "pinecone-test-key")
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
def fake_pinecone_service() -> FakePineconeService:
    """Return an in-memory Pinecone service for tests."""
    return FakePineconeService()


@pytest.fixture
def fake_market_data_bus() -> FakeMarketDataBus:
    """Return an in-memory market bus for tests."""
    return FakeMarketDataBus()


@pytest.fixture
async def client(
    test_settings: Settings,
    fake_cache_service: FakeCacheService,
    fake_pinecone_service: FakePineconeService,
    fake_market_data_bus: FakeMarketDataBus,
) -> AsyncIterator[AsyncClient]:
    """Yield an async test client with lifespan enabled."""
    app = create_app(settings=test_settings)
    app.dependency_overrides[get_cache_service] = lambda: fake_cache_service

    async with LifespanManager(app):
        app.state.pinecone_service = fake_pinecone_service
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
