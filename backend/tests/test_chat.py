"""Chat endpoint tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.cache_keys import chat_history_key
from app.core.llm_factory import LLMFactory
from app.services.chat_service import SYSTEM_SCRATCHPAD_PROMPT


@pytest.mark.asyncio
async def test_get_models(client) -> None:
    """GET /models returns the supported provider catalog."""
    response = await client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    assert "providers" in payload
    assert payload["providers"]
    assert {"name", "models"} <= set(payload["providers"][0])


@pytest.mark.asyncio
async def test_send_message_with_mocked_llm(
    client,
    fake_cache_service,
    user_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /chat/message returns assistant content from a mocked LLM."""
    captured_messages = []

    class FakeLLM:
        async def ainvoke(self, messages):
            captured_messages.extend(messages)
            return SimpleNamespace(
                content="Mocked assistant reply",
                usage_metadata={"total_tokens": 42},
            )

    monkeypatch.setattr(
        LLMFactory,
        "get_llm",
        staticmethod(lambda provider, model_name: FakeLLM()),
    )

    asset_response = await client.post(
        "/api/v1/assets",
        headers=user_headers,
        json={
            "attachments": [
                {
                    "kind": "file",
                    "name": "design-notes.md",
                    "mime_type": "text/markdown",
                    "text_content": (
                        "Hello there from the Button component. It renders a green CTA."
                    ),
                }
            ]
        },
    )
    assert asset_response.status_code == 201

    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o", "title": "Testing"},
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/message",
        headers=user_headers,
        json={
            "conversation_id": conversation_id,
            "content": "Hello there",
            "attachments": [
                {
                    "kind": "file",
                    "name": "component.tsx",
                    "mime_type": "text/x-typescript",
                    "text_content": "export const Button = () => null",
                },
                {
                    "kind": "image",
                    "name": "diagram.png",
                    "mime_type": "image/png",
                    "data_url": "data:image/png;base64,aW1hZ2U=",
                },
            ],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["role"] == "assistant"
    assert payload["content"] == "Mocked assistant reply"
    assert payload["token_count"] == 42

    cache_key = chat_history_key(conversation_id=conversation_id)
    history = fake_cache_service.store[cache_key]
    assert isinstance(history, list)
    assert history[-2]["content"] == "Hello there"
    assert history[-2]["attachments"] == [
        {
            "kind": "file",
            "name": "component.tsx",
            "mime_type": "text/x-typescript",
        },
        {
            "kind": "image",
            "name": "diagram.png",
            "mime_type": "image/png",
        },
    ]
    assert history[-1]["content"] == "Mocked assistant reply"
    assert fake_cache_service.ttl_by_key[cache_key] == 3600
    assert captured_messages[0].content == SYSTEM_SCRATCHPAD_PROMPT
    assert captured_messages[-1].content[0] == {"type": "text", "text": "Hello there"}
    assert captured_messages[-1].content[1] == {
        "type": "text",
        "text": (
            "Attached file: component.tsx\n"
            "MIME type: text/x-typescript\n"
            "export const Button = () => null"
        ),
    }
    assert captured_messages[-1].content[2] == {
        "type": "text",
        "text": "Attached image: diagram.png",
    }
    assert captured_messages[-1].content[3]["type"] == "image_url"

    detail_response = await client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=user_headers,
    )
    detail_payload = detail_response.json()
    assert detail_response.status_code == 200
    assert detail_payload["messages"][0]["attachments"] == [
        {
            "kind": "file",
            "name": "component.tsx",
            "mime_type": "text/x-typescript",
        },
        {
            "kind": "image",
            "name": "diagram.png",
            "mime_type": "image/png",
        },
    ]


@pytest.mark.asyncio
async def test_send_message_returns_structured_404_for_missing_conversation(
    client,
    user_headers,
) -> None:
    """Missing conversations return the unified 404 error envelope."""
    response = await client.post(
        "/api/v1/chat/message",
        headers=user_headers,
        json={
            "conversation_id": "00000000-0000-0000-0000-000000000001",
            "content": "Hello",
        },
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"] == {
        "code": "conversation_not_found",
        "message": "Conversation not found.",
    }


@pytest.mark.asyncio
async def test_send_message_returns_502_for_provider_errors(
    client,
    user_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upstream provider failures are normalized to a structured 502."""

    class FakeLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("provider down")

    monkeypatch.setattr(
        LLMFactory,
        "get_llm",
        staticmethod(lambda provider, model_name: FakeLLM()),
    )

    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o"},
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/message",
        headers=user_headers,
        json={"conversation_id": conversation_id, "content": "Hello there"},
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["error"] == {
        "code": "provider_request_failed",
        "message": "The model provider request failed.",
    }


@pytest.mark.asyncio
async def test_send_message_rejects_image_attachments_for_non_vision_models(
    client,
    user_headers,
) -> None:
    """Image attachments require a provider with image input support."""
    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={
            "provider": "groq",
            "model_name": "llama-3.3-70b-versatile",
        },
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/message",
        headers=user_headers,
        json={
            "conversation_id": conversation_id,
            "content": "",
            "attachments": [
                {
                    "kind": "image",
                    "name": "diagram.png",
                    "mime_type": "image/png",
                    "data_url": "data:image/png;base64,aW1hZ2U=",
                }
            ],
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == {
        "code": "invalid_provider_model",
        "message": (
            "The selected provider/model does not support image attachments. "
            "Choose GPT-4o or Gemini to send images."
        ),
    }


@pytest.mark.asyncio
async def test_stream_message_returns_sse_chunks_and_done_signal(
    client,
    fake_cache_service,
    user_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /chat/stream emits raw SSE chunks and stores the final response."""

    class FakeLLM:
        async def astream(self, messages):
            del messages
            for token in ["Hello", " world"]:
                yield SimpleNamespace(content=token)

    monkeypatch.setattr(
        LLMFactory,
        "get_llm",
        staticmethod(lambda provider, model_name: FakeLLM()),
    )

    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o"},
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/stream",
        headers=user_headers,
        json={"conversation_id": conversation_id, "content": "Stream this"},
    )

    assert response.status_code == 200
    assert "data: Hello\n\n" in response.text
    assert "data:  world\n\n" in response.text
    assert "data: [DONE]\n\n" in response.text

    cache_key = chat_history_key(conversation_id=conversation_id)
    history = fake_cache_service.store[cache_key]
    assert history[-1]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_health_check_returns_200(client) -> None:
    """GET /health returns service health information."""
    response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert {"db", "redis", "version"} <= set(payload)
