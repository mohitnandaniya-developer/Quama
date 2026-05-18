"""MCP connection endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_mcp_connection_service, require_user_id
from app.schemas.mcp import (
    MCPConnectionListResponse,
    MCPConnectionRequest,
    MCPConnectionResponse,
    MCPProviderInfo,
)
from app.services.mcp_connection_service import MCPConnectionService

router = APIRouter()


@router.get("/providers", response_model=list[MCPProviderInfo])
async def list_mcp_providers(
    service: Annotated[MCPConnectionService, Depends(get_mcp_connection_service)],
) -> list[MCPProviderInfo]:
    """Return connectable MCP provider presets."""
    return service.list_providers()


@router.get("/connections", response_model=MCPConnectionListResponse)
async def list_mcp_connections(
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[MCPConnectionService, Depends(get_mcp_connection_service)],
) -> MCPConnectionListResponse:
    """Return the user's active MCP connections."""
    return MCPConnectionListResponse(
        items=await service.list_connections(user_id=user_id)
    )


@router.post(
    "/connections",
    response_model=MCPConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_mcp_provider(
    payload: MCPConnectionRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[MCPConnectionService, Depends(get_mcp_connection_service)],
) -> MCPConnectionResponse:
    """Connect an MCP provider and discover tools."""
    return await service.connect(user_id=user_id, payload=payload)


@router.delete("/connections/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_mcp_provider(
    provider: str,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[MCPConnectionService, Depends(get_mcp_connection_service)],
) -> None:
    """Disconnect an MCP provider."""
    await service.disconnect(user_id=user_id, provider=provider)
