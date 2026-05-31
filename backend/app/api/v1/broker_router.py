"""Broker integration endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import (
    get_broker_registry,
    get_broker_session_service,
    require_user_id,
)
from app.schemas.broker import (
    AngelOneConnectRequest,
    BrokerConnectResponse,
    BrokerDisconnectResponse,
    BrokerPortfolioResponse,
    BrokerStatusItem,
    BrokerStatusResponse,
    GrowwConnectRequest,
)
from app.services.broker_session_service import (
    ANGEL_ONE_BROKER,
    GROWW_BROKER,
    BrokerSessionService,
)
from app.services.brokers.registry import BrokerServiceRegistry

router = APIRouter()


@router.post("/angel-one/connect", response_model=BrokerConnectResponse)
async def connect_angel_one(
    payload: AngelOneConnectRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerConnectResponse:
    """Connect an Angel One broker account."""
    broker = registry.get(ANGEL_ONE_BROKER)
    return await broker.connect(
        user_id=user_id,
        client_code=payload.client_code,
        password=payload.password,
        totp=payload.totp,
    )


@router.delete(
    "/angel-one/disconnect",
    response_model=BrokerDisconnectResponse,
)
async def disconnect_angel_one(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerDisconnectResponse:
    """Disconnect the active Angel One broker session."""
    broker = registry.get(ANGEL_ONE_BROKER)
    await broker.disconnect(user_id=user_id)
    return BrokerDisconnectResponse(disconnected=True)


@router.get("/status", response_model=BrokerStatusResponse)
async def broker_status(
    user_id: Annotated[str, Depends(require_user_id)],
    service: Annotated[BrokerSessionService, Depends(get_broker_session_service)],
) -> BrokerStatusResponse:
    """Return connected broker status for the current user."""
    rows = await service.list_active_sessions(user_id=user_id)
    return BrokerStatusResponse(
        items=[
            BrokerStatusItem(
                broker=row.broker,
                client_code=row.client_code,
                connected_at=row.connected_at,
                is_active=row.is_active,
            )
            for row in rows
        ]
    )


@router.get("/angel-one/holdings")
async def angel_one_holdings(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> list[dict[str, Any]]:
    """Return Angel One holdings."""
    broker = registry.get(ANGEL_ONE_BROKER)
    return await broker.get_holdings(
        user_id=user_id,
        trigger="user_action",
        force_refresh=False,
    )


@router.get("/angel-one/positions")
async def angel_one_positions(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> list[dict[str, Any]]:
    """Return Angel One positions."""
    broker = registry.get(ANGEL_ONE_BROKER)
    return await broker.get_positions(
        user_id=user_id,
        trigger="user_action",
        force_refresh=False,
    )


@router.get("/angel-one/funds")
async def angel_one_funds(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> dict[str, Any]:
    """Return Angel One funds / margin limits."""
    broker = registry.get(ANGEL_ONE_BROKER)
    return await broker.get_funds(
        user_id=user_id,
        trigger="user_action",
        force_refresh=False,
    )


@router.get("/angel-one/portfolio", response_model=BrokerPortfolioResponse)
async def angel_one_portfolio(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerPortfolioResponse:
    """Return Angel One portfolio summary."""
    try:
        broker = registry.get(ANGEL_ONE_BROKER)
        payload = await broker.get_portfolio(
            user_id=user_id,
            trigger="user_action",
            force_refresh=False,
        )
    except Exception as exc:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(
            "Angel One portfolio fetch failed for user %s: %s",
            user_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503, detail=f"Unable to fetch Angel One portfolio: {str(exc)}"
        ) from exc

    return BrokerPortfolioResponse(
        holdings=payload["holdings"],
        funds=payload["funds"],
        summary={
            "funds": payload["summary"].get("funds"),
            "investment": payload["summary"].get("investment"),
            "overall_gain": payload["summary"].get("overall_gain"),
        },
        connected_broker=payload.get("broker", ANGEL_ONE_BROKER),
        performance_history=payload.get("performance_history", []),
    )


@router.post("/groww/connect", response_model=BrokerConnectResponse)
async def connect_groww(
    payload: GrowwConnectRequest,
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerConnectResponse:
    """Connect a Groww broker account."""
    broker = registry.get(GROWW_BROKER)
    return await broker.connect(
        user_id=user_id,
        client_code=payload.api_key,
        password="",
        totp=payload.totp,
    )


@router.delete(
    "/groww/disconnect",
    response_model=BrokerDisconnectResponse,
)
async def disconnect_groww(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerDisconnectResponse:
    """Disconnect the active Groww broker session."""
    broker = registry.get(GROWW_BROKER)
    await broker.disconnect(user_id=user_id)
    return BrokerDisconnectResponse(disconnected=True)


@router.get("/groww/portfolio", response_model=BrokerPortfolioResponse)
async def groww_portfolio(
    user_id: Annotated[str, Depends(require_user_id)],
    registry: Annotated[BrokerServiceRegistry, Depends(get_broker_registry)],
) -> BrokerPortfolioResponse:
    """Return Groww portfolio summary."""
    broker = registry.get(GROWW_BROKER)
    payload = await broker.get_portfolio(
        user_id=user_id,
        trigger="user_action",
        force_refresh=True,
    )
    return BrokerPortfolioResponse(
        holdings=payload["holdings"],
        funds=payload["funds"],
        summary={
            "funds": payload["summary"].get("funds"),
            "investment": payload["summary"].get("investment"),
            "overall_gain": payload["summary"].get("overall_gain"),
        },
        connected_broker=GROWW_BROKER,
        performance_history=payload.get("performance_history", []),
    )
