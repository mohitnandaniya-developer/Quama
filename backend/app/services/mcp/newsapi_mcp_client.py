"""Backend-owned NewsAPI.ai MCP stdio client."""

from __future__ import annotations

import json
import os
from contextlib import AsyncExitStack
from typing import Any

from app.config import Settings

ALLOWED_NEWSAPI_TOOLS = {
    "suggest",
    "search_articles",
    "search_events",
    "get_topic_page_articles",
    "get_topic_page_events",
}


class NewsApiMCPClient:
    """Connect to the fixed NewsAPI MCP server over stdio.

    Backend should act as a safe MCP proxy.

    Frontend must not directly control MCP server command, args, or env.
    Frontend only calls backend endpoints.
    Backend owns the NewsAPI key, MCP server startup, and tool validation.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session: Any | None = None
        self.exit_stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        """Start `npx -y newsapi-mcp` and initialize an MCP session."""
        if not self.settings.newsapi_key.strip():
            msg = "NewsAPI key is not configured"
            raise RuntimeError(msg)

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:
            msg = "Python package 'mcp' is not installed"
            raise RuntimeError(msg) from exc

        env = os.environ.copy()
        # App config accepts only NEWS_API_KEY. The npm MCP server expects
        # NEWSAPI_KEY in its child-process environment.
        env["NEWSAPI_KEY"] = self.settings.newsapi_key.strip()
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "newsapi-mcp"],
            env=env,
        )

        self.exit_stack = AsyncExitStack()
        read_stream, write_stream = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return allowed NewsAPI tool names and descriptions."""
        self._require_session()
        result = await self.session.list_tools()
        tools = getattr(result, "tools", result)
        normalized: list[dict[str, Any]] = []
        for tool in tools or []:
            name = str(getattr(tool, "name", "")).strip()
            if name not in ALLOWED_NEWSAPI_TOOLS:
                continue
            input_schema = getattr(tool, "inputSchema", None) or getattr(
                tool,
                "input_schema",
                {},
            )
            normalized.append(
                {
                    "name": name,
                    "description": str(getattr(tool, "description", "") or ""),
                    "input_schema": self._json_safe(input_schema),
                }
            )
        return normalized

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Validate and call one NewsAPI MCP tool."""
        self._require_session()
        if tool_name not in ALLOWED_NEWSAPI_TOOLS:
            msg = "Invalid MCP tool"
            raise ValueError(msg)
        result = await self.session.call_tool(
            tool_name,
            self._normalize_arguments(tool_name, arguments or {}),
        )
        safe_result = self._json_safe(result)
        if isinstance(safe_result, dict) and safe_result.get("isError"):
            raise RuntimeError(self._extract_error_message(safe_result))
        return safe_result

    async def close(self) -> None:
        """Clean up the MCP session and subprocess."""
        if self.exit_stack is not None:
            await self.exit_stack.aclose()
        self.session = None
        self.exit_stack = None

    def _require_session(self) -> None:
        if self.session is None:
            msg = "NewsAPI MCP client is not connected"
            raise RuntimeError(msg)

    @classmethod
    def _normalize_arguments(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Map frontend-friendly names to the NewsAPI MCP tool schema."""
        normalized = dict(arguments)

        mapped_query = False
        query_value = normalized.get("query")
        if isinstance(query_value, str):
            normalized.setdefault("keyword", cls._keyword_from_text(query_value))
            normalized.pop("query", None)
            mapped_query = True

        keyword_value = normalized.get("keyword")
        should_normalize_keyword = (
            isinstance(keyword_value, str)
            and not mapped_query
            and "," not in keyword_value
        )
        if should_normalize_keyword:
            normalized["keyword"] = cls._keyword_from_text(keyword_value)
            normalized.setdefault("keywordOper", "and")
        elif isinstance(keyword_value, str):
            normalized.setdefault("keywordOper", "and")

        rename_map = {
            "language": "lang",
            "date_start": "dateStart",
            "date_end": "dateEnd",
            "source_uri": "sourceUri",
            "category_uri": "categoryUri",
        }
        for old_name, new_name in rename_map.items():
            if old_name in normalized and new_name not in normalized:
                normalized[new_name] = normalized.pop(old_name)

        max_results = normalized.pop("max_results", None)
        if max_results is not None:
            count_key = (
                "eventsCount" if tool_name == "search_events" else "articlesCount"
            )
            normalized.setdefault(count_key, max_results)

        return {key: value for key, value in normalized.items() if value is not None}

    @staticmethod
    def _keyword_from_text(value: str) -> str:
        """Turn a natural-language prompt into NewsAPI keyword filters."""
        cleaned = "".join(char if char.isalnum() else " " for char in value.lower())
        replacements = {
            "reliance": "Reliance Industries",
            "relience": "Reliance Industries",
        }
        stopwords = {
            "a",
            "about",
            "am",
            "and",
            "are",
            "buy",
            "can",
            "do",
            "for",
            "from",
            "give",
            "i",
            "in",
            "is",
            "latest",
            "me",
            "news",
            "not",
            "of",
            "or",
            "please",
            "review",
            "should",
            "show",
            "tell",
            "the",
            "to",
            "want",
            "what",
            "whether",
        }
        tokens: list[str] = []
        for raw_token in cleaned.split():
            token = replacements.get(raw_token, raw_token)
            if len(token) < 2 or token in stopwords:
                continue
            if token not in tokens:
                tokens.append(token)
            if len(tokens) >= 6:
                break
        if "Reliance Industries" in tokens and "India" not in tokens:
            tokens.append("India")
        return ", ".join(tokens) if tokens else value.strip()

    @staticmethod
    def _extract_error_message(result: dict[str, Any]) -> str:
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    return item["text"]
        return "NewsAPI MCP tool call failed"

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        """Convert MCP SDK response objects into JSON-safe data."""
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, list | tuple | set):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if hasattr(value, "model_dump"):
            return cls._json_safe(value.model_dump())
        if hasattr(value, "__dict__"):
            return cls._json_safe(vars(value))
        try:
            return json.loads(json.dumps(value, default=str))
        except TypeError:
            return str(value)
