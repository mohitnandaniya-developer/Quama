"""Conversation endpoint tests."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_conversation_returns_201(client, user_headers) -> None:
    """POST /conversations creates a conversation."""
    response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o", "title": "My chat"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == "My chat"
    assert payload["provider"] == "openai"
    assert payload["model_name"] == "gpt-4o"


@pytest.mark.asyncio
async def test_create_conversation_rewrites_deprecated_groq_alias(
    client,
    user_headers,
) -> None:
    """Deprecated Groq aliases are persisted as the canonical supported model."""
    response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={
            "provider": "groq",
            "model_name": "llama-3.1-70b-versatile",
            "title": "Legacy Groq chat",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "groq"
    assert payload["model_name"] == "llama-3.3-70b-versatile"


@pytest.mark.asyncio
async def test_list_conversations_returns_paginated_envelope(
    client,
    user_headers,
) -> None:
    """GET /conversations returns a paginated envelope."""
    await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "google", "model_name": "gemini-1.5-pro"},
    )

    response = await client.get(
        "/api/v1/conversations?skip=0&limit=10",
        headers=user_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert {"items", "total", "skip", "limit"} <= set(payload)
    assert isinstance(payload["items"], list)


@pytest.mark.asyncio
async def test_list_conversations_keeps_total_for_out_of_range_page(
    client,
    user_headers,
) -> None:
    """An empty page should still report the number of matching rows."""
    await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "google", "model_name": "gemini-1.5-pro"},
    )

    response = await client.get(
        "/api/v1/conversations?skip=10&limit=10",
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 1


@pytest.mark.asyncio
async def test_create_conversation_rejects_unknown_fields(
    client,
    user_headers,
) -> None:
    """Unknown request fields return the unified validation error envelope."""
    response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={
            "provider": "openai",
            "model_name": "gpt-4o",
            "title": "Strict payload",
            "extra": "nope",
        },
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_create_conversation_rejects_invalid_provider_model(
    client,
    user_headers,
) -> None:
    """Unsupported provider/model pairs return a structured 422."""
    response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "not-a-model"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"] == {
        "code": "invalid_provider_model",
        "message": "Unsupported model 'not-a-model' for provider 'openai'.",
    }


@pytest.mark.asyncio
async def test_delete_conversation_returns_204(client, user_headers) -> None:
    """DELETE /conversations soft-deletes and returns 204."""
    create_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o"},
    )
    conversation_id = create_response.json()["id"]

    response = await client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=user_headers,
    )

    assert response.status_code == 204
    assert response.text == ""


@pytest.mark.asyncio
async def test_get_conversation_returns_structured_404(client, user_headers) -> None:
    """Missing conversations use the unified not-found error shape."""
    response = await client.get(
        f"/api/v1/conversations/{uuid.uuid4()}",
        headers=user_headers,
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"] == {
        "code": "conversation_not_found",
        "message": "Conversation not found.",
    }
