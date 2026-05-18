"""User-scoped MCP connection registry."""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.core.cache_keys import mcp_connection_key, mcp_connections_index_key
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import MCPConnectionError
from app.schemas.mcp import (
    MCPConnectionRequest,
    MCPConnectionResponse,
    MCPProviderInfo,
    MCPToolMetadata,
)
from app.services.cache_service import CacheService
from app.services.mcp.newsapi_mcp_client import NewsApiMCPClient
from app.services.mcp_client import MCPClient, MCPTransport

DEFAULT_MCP_CONNECTION_TTL_SECONDS = 30 * 24 * 60 * 60

PROVIDER_CATALOG: dict[str, MCPProviderInfo] = {
    "zerodha": MCPProviderInfo(
        provider="zerodha",
        label="Zerodha",
        description="Portfolio, holdings, funds, and positions via MCP tools.",
        transport="mock",
    ),
    "github": MCPProviderInfo(
        provider="github",
        label="GitHub",
        description="Repository and profile tools exposed through MCP.",
        transport="mock",
    ),
    "newsapi": MCPProviderInfo(
        provider="newsapi",
        label="NewsAPI.ai",
        description="Search current articles, events, topic pages, and suggestions.",
        transport="mock",
    ),
}


class MCPConnectionService:
    """Persist user MCP connections and discovered tool metadata."""

    def __init__(
        self,
        *,
        cache_service: CacheService,
        settings: Settings,
        connection_ttl_seconds: int = DEFAULT_MCP_CONNECTION_TTL_SECONDS,
    ) -> None:
        self.cache_service = cache_service
        self.settings = settings
        self.connection_ttl_seconds = max(int(connection_ttl_seconds), 1)

    def list_providers(self) -> list[MCPProviderInfo]:
        """Return known connectable MCP provider presets."""
        return list(PROVIDER_CATALOG.values())

    async def connect(
        self,
        *,
        user_id: str,
        payload: MCPConnectionRequest,
    ) -> MCPConnectionResponse:
        """Connect a provider, discover tools, and store metadata."""
        provider = payload.provider.strip().lower()
        catalog_item = PROVIDER_CATALOG.get(provider)
        label = catalog_item.label if catalog_item else provider.title()
        if provider == "newsapi":
            return await self._connect_newsapi(user_id=user_id, label=label)

        transport: MCPTransport = payload.transport
        client = MCPClient(
            provider=provider,
            transport=transport,
            server_url=payload.server_url,
            access_token=payload.access_token,
        )
        tools = await client.list_tools()
        if not tools:
            raise MCPConnectionError("MCP provider did not expose any tools.")

        record = {
            "provider": provider,
            "label": label,
            "transport": transport,
            "server_url": payload.server_url,
            "access_token": (
                encrypt(payload.access_token) if payload.access_token else ""
            ),
            "tools": [tool.model_dump() for tool in tools],
        }
        await self._store_connection(user_id=user_id, provider=provider, record=record)
        return self._to_response(record)

    async def disconnect(self, *, user_id: str, provider: str) -> None:
        """Remove one MCP connection for a user."""
        normalized_provider = provider.strip().lower()
        await self.cache_service.delete(
            mcp_connection_key(user_id=user_id, provider=normalized_provider)
        )
        providers = await self._load_provider_index(user_id=user_id)
        await self._store_provider_index(
            user_id=user_id,
            providers=[item for item in providers if item != normalized_provider],
        )

    async def list_connections(self, *, user_id: str) -> list[MCPConnectionResponse]:
        """Return active MCP connections with public metadata only."""
        records = await self._load_connection_records(user_id=user_id)
        return [self._to_response(record) for record in records]

    async def list_tools(self, *, user_id: str) -> list[tuple[str, MCPToolMetadata]]:
        """Return all tools attached to a user context."""
        records = await self._load_connection_records(user_id=user_id)
        tools: list[tuple[str, MCPToolMetadata]] = []
        for record in records:
            provider = str(record.get("provider", ""))
            for raw_tool in record.get("tools", []):
                if isinstance(raw_tool, dict):
                    tools.append((provider, MCPToolMetadata(**raw_tool)))
        return tools

    async def call_tool(
        self,
        *,
        user_id: str,
        provider: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Call one MCP tool for a connected provider."""
        record = await self._load_connection_record(user_id=user_id, provider=provider)
        if record is None:
            raise MCPConnectionError(f"{provider} is not connected.")
        if str(record["provider"]) == "newsapi":
            client = NewsApiMCPClient(self.settings)
            try:
                await client.connect()
                return await client.call_tool(tool_name, arguments)
            except Exception as exc:
                raise MCPConnectionError("NewsAPI MCP tool call failed.") from exc
            finally:
                await client.close()

        client = MCPClient(
            provider=str(record["provider"]),
            transport=record["transport"],
            server_url=record.get("server_url"),
            access_token=self._decrypt_optional(str(record.get("access_token") or "")),
        )
        return await client.call_tool(tool_name=tool_name, arguments=arguments)

    async def is_connected(self, *, user_id: str, provider: str) -> bool:
        """Return whether a provider is active for the user."""
        record = await self._load_connection_record(user_id=user_id, provider=provider)
        return record is not None

    async def _connect_newsapi(
        self,
        *,
        user_id: str,
        label: str,
    ) -> MCPConnectionResponse:
        client = NewsApiMCPClient(self.settings)
        try:
            await client.connect()
            raw_tools = await client.list_tools()
        except Exception as exc:
            raise MCPConnectionError(f"NewsAPI MCP connection failed: {exc}") from exc
        finally:
            await client.close()

        tools = [
            MCPToolMetadata(
                name=str(tool.get("name", "")),
                description=str(tool.get("description", "")),
                input_schema=tool.get("input_schema", {})
                if isinstance(tool.get("input_schema", {}), dict)
                else {},
            )
            for tool in raw_tools
            if isinstance(tool, dict) and str(tool.get("name", "")).strip()
        ]
        if not tools:
            raise MCPConnectionError("NewsAPI MCP provider did not expose any tools.")

        record = {
            "provider": "newsapi",
            "label": label,
            "transport": "mock",
            "server_url": None,
            "access_token": "",
            "tools": [tool.model_dump() for tool in tools],
        }
        await self._store_connection(user_id=user_id, provider="newsapi", record=record)
        return self._to_response(record)

    async def _store_connection(
        self,
        *,
        user_id: str,
        provider: str,
        record: dict[str, Any],
    ) -> None:
        saved = await self.cache_service.set(
            mcp_connection_key(user_id=user_id, provider=provider),
            record,
            self.connection_ttl_seconds,
        )
        if not saved:
            raise MCPConnectionError("Unable to persist MCP connection.")
        providers = await self._load_provider_index(user_id=user_id)
        if provider not in providers:
            providers.append(provider)
        if not await self._store_provider_index(
            user_id=user_id,
            providers=providers,
        ):
            await self.cache_service.delete(
                mcp_connection_key(user_id=user_id, provider=provider)
            )
            raise MCPConnectionError("Unable to persist MCP connection index.")

    async def _load_connection_records(self, *, user_id: str) -> list[dict[str, Any]]:
        providers = await self._load_provider_index(user_id=user_id)
        records: list[dict[str, Any]] = []
        for provider in providers:
            record = await self._load_connection_record(
                user_id=user_id,
                provider=provider,
            )
            if record is not None:
                records.append(record)
        return records

    async def _load_connection_record(
        self,
        *,
        user_id: str,
        provider: str,
    ) -> dict[str, Any] | None:
        record = await self.cache_service.get(
            mcp_connection_key(user_id=user_id, provider=provider.strip().lower())
        )
        return record if isinstance(record, dict) else None

    async def _load_provider_index(self, *, user_id: str) -> list[str]:
        providers = await self.cache_service.get(
            mcp_connections_index_key(user_id=user_id)
        )
        if not isinstance(providers, list):
            return []
        return [str(provider) for provider in providers if str(provider).strip()]

    async def _store_provider_index(
        self,
        *,
        user_id: str,
        providers: list[str],
    ) -> bool:
        return await self.cache_service.set(
            mcp_connections_index_key(user_id=user_id),
            sorted(set(providers)),
            self.connection_ttl_seconds,
        )

    def _to_response(self, record: dict[str, Any]) -> MCPConnectionResponse:
        tools = [
            MCPToolMetadata(**tool)
            for tool in record.get("tools", [])
            if isinstance(tool, dict)
        ]
        return MCPConnectionResponse(
            provider=str(record["provider"]),
            label=str(record["label"]),
            transport=record["transport"],
            server_url=record.get("server_url"),
            connected=True,
            tools=tools,
        )

    @staticmethod
    def _decrypt_optional(value: str) -> str | None:
        if not value:
            return None
        return decrypt(value)
