"""Schemas for MCP tool connections and agent calls."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ProviderId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ToolName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MCPToolMetadata(BaseModel):
    """One MCP tool exposed to the agent."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPProviderInfo(BaseModel):
    """Frontend catalog item for a connectable MCP provider."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    label: str
    description: str
    transport: Literal["mock", "http_jsonrpc"]
    server_url: str | None = None


class MCPConnectionRequest(BaseModel):
    """Connect one user to an MCP provider."""

    model_config = ConfigDict(extra="forbid")

    provider: ProviderId
    transport: Literal["mock", "http_jsonrpc"] = "mock"
    server_url: str | None = None
    access_token: str | None = None


class MCPConnectionResponse(BaseModel):
    """Connected MCP provider with discovered tools."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    label: str
    transport: Literal["mock", "http_jsonrpc"]
    server_url: str | None = None
    connected: bool
    tools: list[MCPToolMetadata]


class MCPConnectionListResponse(BaseModel):
    """List of active MCP connections for a user."""

    model_config = ConfigDict(extra="forbid")

    items: list[MCPConnectionResponse]


class AgentQueryRequest(BaseModel):
    """User query routed through the MCP agent controller."""

    model_config = ConfigDict(extra="forbid")

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AgentToolCall(BaseModel):
    """One MCP tool call made while answering a query."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    tool: str
    arguments: dict[str, Any]
    result: Any


class AgentQueryResponse(BaseModel):
    """Agent answer plus structured tool-call trace."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    tool_calls: list[AgentToolCall] = Field(default_factory=list)
    available_tools: list[MCPToolMetadata] = Field(default_factory=list)
