"""Small MCP client abstraction for tool discovery and invocation."""

from __future__ import annotations

# MOCK IMPLEMENTATION: the mock transport is intentionally retained for local
# tool development until provider-backed MCP servers are configured.
import uuid
from typing import Any, Literal

import httpx

from app.core.exceptions import MCPConnectionError, MCPToolNotFoundError
from app.schemas.mcp import MCPToolMetadata

MCPTransport = Literal["mock", "http_jsonrpc"]


class MCPClient:
    """Connect to either a mock provider or an HTTP JSON-RPC MCP endpoint."""

    def __init__(
        self,
        *,
        provider: str,
        transport: MCPTransport,
        server_url: str | None = None,
        access_token: str | None = None,
    ) -> None:
        self.provider = provider
        self.transport = transport
        self.server_url = server_url.strip() if server_url else None
        self.access_token = access_token.strip() if access_token else None

    async def list_tools(self) -> list[MCPToolMetadata]:
        """Return available MCP tools."""
        if self.transport == "mock":
            return _mock_tools(self.provider)

        result = await self._json_rpc(method="tools/list", params={})
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list):
            raise MCPConnectionError(
                "MCP server returned an invalid tools/list result."
            )
        return [_normalize_tool(tool) for tool in tools if isinstance(tool, dict)]

    async def call_tool(self, *, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invoke one MCP tool and return its structured result."""
        if self.transport == "mock":
            return _call_mock_tool(
                provider=self.provider,
                tool_name=tool_name,
                arguments=arguments,
            )

        return await self._json_rpc(
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
        )

    async def _json_rpc(self, *, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.server_url:
            raise MCPConnectionError("server_url is required for HTTP MCP transport.")

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": method,
            "params": params,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.server_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                decoded = response.json()
        except Exception as exc:
            raise MCPConnectionError(f"MCP request failed: {exc}") from exc

        if not isinstance(decoded, dict):
            raise MCPConnectionError("MCP server returned a non-object response.")
        error = decoded.get("error")
        if error:
            raise MCPConnectionError(f"MCP server error: {error}")
        result = decoded.get("result")
        if not isinstance(result, dict):
            raise MCPConnectionError("MCP server returned an invalid result.")
        return result


def _normalize_tool(raw: dict[str, Any]) -> MCPToolMetadata:
    input_schema = raw.get("inputSchema") or raw.get("input_schema") or {}
    return MCPToolMetadata(
        name=str(raw.get("name", "")).strip(),
        description=str(raw.get("description", "")).strip(),
        input_schema=input_schema if isinstance(input_schema, dict) else {},
    )


def _mock_tools(provider: str) -> list[MCPToolMetadata]:
    if provider == "zerodha":
        return [
            MCPToolMetadata(
                name="get_portfolio",
                description="Return holdings, cash, and total portfolio value.",
                input_schema={"type": "object", "properties": {}},
            ),
            MCPToolMetadata(
                name="get_positions",
                description="Return current intraday and overnight positions.",
                input_schema={"type": "object", "properties": {}},
            ),
        ]
    # Only Zerodha mock tools are provided for now.
    raise MCPConnectionError(f"Unknown mock MCP provider: {provider}")


def _call_mock_tool(
    *,
    provider: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    del arguments
    if provider == "zerodha" and tool_name == "get_portfolio":
        return {
            "currency": "INR",
            "total_value": 845250.75,
            "cash": 54200.0,
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "quantity": 15,
                    "last_price": 2925.4,
                    "market_value": 43881.0,
                },
                {
                    "symbol": "INFY",
                    "quantity": 40,
                    "last_price": 1492.65,
                    "market_value": 59706.0,
                },
                {
                    "symbol": "HDFCBANK",
                    "quantity": 25,
                    "last_price": 1531.2,
                    "market_value": 38280.0,
                },
            ],
        }
    if provider == "zerodha" and tool_name == "get_positions":
        return {"positions": [], "message": "No open positions in the mock account."}
    # No GitHub mock responses — only Zerodha is supported by the mock transport.
    raise MCPToolNotFoundError(f"Tool {tool_name} is not available for {provider}.")
