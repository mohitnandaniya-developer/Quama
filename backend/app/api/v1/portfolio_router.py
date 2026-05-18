"""Portfolio pipeline endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_portfolio_sync_service, require_user_id
from app.schemas.portfolio import PortfolioSnapshotResponse, PortfolioSyncRequest
from app.schemas.portfolio_history import PortfolioHistoryResponse
from app.services.portfolio_sync_service import PortfolioSyncService

router = APIRouter()


@router.post("/sync", response_model=PortfolioSnapshotResponse)
async def sync_portfolio(
    payload: PortfolioSyncRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[PortfolioSyncService, Depends(get_portfolio_sync_service)],
) -> PortfolioSnapshotResponse:
    """Synchronize and return the current portfolio snapshot."""
    snapshot = await service.get_portfolio_snapshot(
        user_id=user_id,
        trigger=payload.trigger,
        force_refresh=payload.force_refresh,
    )
    return PortfolioSnapshotResponse(**snapshot)


@router.get("/{broker}/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    broker: str,
    period: str,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[PortfolioSyncService, Depends(get_portfolio_sync_service)],
) -> PortfolioHistoryResponse:
    """Fetch dynamic historical performance data."""
    history = await service.get_portfolio_history(
        user_id=user_id,
        broker=broker,
        period=period,
    )
    return PortfolioHistoryResponse(period=period, history=history)
