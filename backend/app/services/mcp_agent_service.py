"""Simple agent controller that can invoke connected MCP tools."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.mcp import AgentQueryResponse, AgentToolCall, MCPToolMetadata
from app.services.mcp_connection_service import MCPConnectionService


class MCPAgentService:
    """Route user intent to connected MCP tools."""

    def __init__(self, *, connection_service: MCPConnectionService) -> None:
        self.connection_service = connection_service

    async def query(self, *, user_id: str, message: str) -> AgentQueryResponse:
        """Answer a user query by selecting and invoking an MCP tool when useful."""
        tools = await self.connection_service.list_tools(user_id=user_id)
        available_tools = [
            MCPToolMetadata(
                name=f"{provider}.{tool.name}",
                description=tool.description,
                input_schema=tool.input_schema,
            )
            for provider, tool in tools
        ]
        if not tools:
            return AgentQueryResponse(
                answer="No MCP tools are connected. Connect Zerodha first.",
                available_tools=[],
            )

        selection = self._select_tool(message=message, tools=tools)
        if selection is None:
            return AgentQueryResponse(
                answer=self._describe_tools(available_tools),
                available_tools=available_tools,
            )

        provider, tool = selection
        arguments: dict[str, Any] = {}
        result = await self.connection_service.call_tool(
            user_id=user_id,
            provider=provider,
            tool_name=tool.name,
            arguments=arguments,
        )
        return AgentQueryResponse(
            answer=self._summarize_tool_result(
                provider=provider,
                tool_name=tool.name,
                result=result,
            ),
            tool_calls=[
                AgentToolCall(
                    provider=provider,
                    tool=tool.name,
                    arguments=arguments,
                    result=result,
                )
            ],
            available_tools=available_tools,
        )

    def _select_tool(
        self,
        *,
        message: str,
        tools: list[tuple[str, MCPToolMetadata]],
    ) -> tuple[str, MCPToolMetadata] | None:
        normalized = message.lower()
        ranked_tool_names: list[str] = []
        if any(term in normalized for term in ("portfolio", "holding", "holdings")):
            ranked_tool_names.extend(["get_portfolio", "get_holdings"])
        if "position" in normalized:
            ranked_tool_names.append("get_positions")
        # Repository/profile queries are not supported (GitHub removed).
        if any(term in normalized for term in ("tool", "tools", "capabilities")):
            return None

        for preferred_name in ranked_tool_names:
            for provider, tool in tools:
                if tool.name == preferred_name:
                    return provider, tool
        return None

    @staticmethod
    def _describe_tools(tools: list[MCPToolMetadata]) -> str:
        names = ", ".join(tool.name for tool in tools)
        return f"Connected MCP tools: {names}."

    @staticmethod
    def _summarize_tool_result(*, provider: str, tool_name: str, result: Any) -> str:
        if provider == "zerodha" and tool_name == "get_portfolio":
            if isinstance(result, dict):
                total = result.get("total_value")
                currency = result.get("currency", "INR")
                holdings = result.get("holdings")
                holding_count = len(holdings) if isinstance(holdings, list) else 0
                return (
                    f"Zerodha portfolio: {currency} {total} total value across "
                    f"{holding_count} holdings."
                )
        # GitHub tool summaries removed — default to generic formatting.
        return f"{provider}.{tool_name} returned: {json.dumps(result, default=str)}"
