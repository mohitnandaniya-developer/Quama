"""Agent endpoints backed by connected MCP tools."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_mcp_agent_service, require_user_id
from app.schemas.mcp import AgentQueryRequest, AgentQueryResponse
from app.services.mcp_agent_service import MCPAgentService

router = APIRouter()


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(
    payload: AgentQueryRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[MCPAgentService, Depends(get_mcp_agent_service)],
) -> AgentQueryResponse:
    """Route a user query through the MCP agent controller."""
    return await service.query(user_id=user_id, message=payload.message)
