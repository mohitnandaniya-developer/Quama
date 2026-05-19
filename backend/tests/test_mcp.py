"""Tests for MCP connection and agent tool invocation."""

from __future__ import annotations

from httpx import AsyncClient

from app.core.cache_keys import mcp_connection_key, mcp_connections_index_key


async def test_mcp_provider_connection_discovers_tools(
    client: AsyncClient,
    fake_cache_service,
    test_settings,
    user_headers: dict[str, str],
) -> None:
    providers_response = await client.get("/api/v1/mcp/providers")

    assert providers_response.status_code == 200
    providers = providers_response.json()
    assert {provider["provider"] for provider in providers} == {
        "zerodha",
        "newsapi",
    }

    connect_response = await client.post(
        "/api/v1/mcp/connections",
        headers=user_headers,
        json={"provider": "zerodha", "transport": "mock"},
    )

    assert connect_response.status_code == 201
    payload = connect_response.json()
    assert payload["provider"] == "zerodha"
    assert payload["connected"] is True
    assert [tool["name"] for tool in payload["tools"]] == [
        "get_portfolio",
        "get_positions",
    ]

    list_response = await client.get(
        "/api/v1/mcp/connections",
        headers=user_headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["provider"] == "zerodha"
    assert (
        fake_cache_service.ttl_by_key[
            mcp_connection_key(user_id="test-user", provider="zerodha")
        ]
        == test_settings.mcp_connection_ttl_seconds
    )
    assert (
        fake_cache_service.ttl_by_key[mcp_connections_index_key(user_id="test-user")]
        == test_settings.mcp_connection_ttl_seconds
    )


async def test_agent_query_invokes_zerodha_portfolio_tool(
    client: AsyncClient,
    user_headers: dict[str, str],
) -> None:
    await client.post(
        "/api/v1/mcp/connections",
        headers=user_headers,
        json={"provider": "zerodha", "transport": "mock"},
    )

    response = await client.post(
        "/api/v1/agent/query",
        headers=user_headers,
        json={"message": "Show my portfolio"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Zerodha portfolio" in payload["answer"]
    assert payload["tool_calls"][0]["provider"] == "zerodha"
    assert payload["tool_calls"][0]["tool"] == "get_portfolio"
    assert payload["tool_calls"][0]["result"]["currency"] == "INR"


async def test_agent_query_lists_tools_when_no_tool_matches(
    client: AsyncClient,
    user_headers: dict[str, str],
) -> None:
    await client.post(
        "/api/v1/mcp/connections",
        headers=user_headers,
        json={"provider": "zerodha", "transport": "mock"},
    )

    response = await client.post(
        "/api/v1/agent/query",
        headers=user_headers,
        json={"message": "What tools are available?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "zerodha.get_portfolio" in payload["answer"]
    assert payload["tool_calls"] == []
