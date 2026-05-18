"""Market-data control plane and SSE gateway endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.core.streaming import iter_sse_events
from app.dependencies import get_market_data_gateway_service, require_user_id
from app.schemas.market import MarketSubscriptionRequest, MarketSubscriptionResponse
from app.services.market_data_gateway_service import MarketDataGatewayService

router = APIRouter()


@router.post("/subscriptions", response_model=MarketSubscriptionResponse)
async def register_market_subscriptions(
    payload: MarketSubscriptionRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[
        MarketDataGatewayService,
        Depends(get_market_data_gateway_service),
    ],
) -> MarketSubscriptionResponse:
    """Register or replace the desired live market subscriptions for a user."""
    response = await service.register_subscriptions(
        user_id=user_id,
        mode=payload.mode,
        replace=payload.replace,
        instruments=[
            {
                "exchange_type": item.exchange_type,
                "instrument_token": item.instrument_token,
            }
            for item in payload.instruments
        ],
    )
    return MarketSubscriptionResponse(**response)


@router.get("/stream")
async def stream_market_data(
    instrument_token: Annotated[list[str], Query(min_length=1)],
    request: Request,
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[
        MarketDataGatewayService,
        Depends(get_market_data_gateway_service),
    ],
) -> StreamingResponse:
    """Bridge Redis market channels to the frontend over SSE."""
    del user_id
    return StreamingResponse(
        iter_sse_events(
            service.stream_payloads(instrument_tokens=sorted(set(instrument_token))),
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
    )
