"""Angel One implementation of the broker abstraction."""

from __future__ import annotations

from typing import Any

from app.schemas.broker import BrokerConnectResponse
from app.services.broker_session_service import ANGEL_ONE_BROKER, BrokerSessionService
from app.services.brokers.base import BaseBrokerService
from app.services.portfolio_sync_service import PortfolioSyncService


class AngelOneBrokerService(BaseBrokerService):
    """Broker adapter that keeps existing Angel One behavior unchanged."""

    broker_name = ANGEL_ONE_BROKER

    def __init__(
        self,
        *,
        broker_session_service: BrokerSessionService,
        portfolio_sync_service: PortfolioSyncService,
    ) -> None:
        self.broker_session_service = broker_session_service
        self.portfolio_sync_service = portfolio_sync_service

    async def connect(
        self,
        *,
        user_id: str,
        client_code: str,
        password: str,
        totp: str,
    ) -> BrokerConnectResponse:
        return await self.broker_session_service.connect_angel_one(
            user_id=user_id,
            client_code=client_code,
            password=password,
            totp=totp,
        )

    async def disconnect(self, *, user_id: str) -> None:
        await self.broker_session_service.disconnect(
            user_id=user_id,
            broker=self.broker_name,
        )

    async def get_portfolio(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> dict[str, Any]:
        return await self.portfolio_sync_service.get_portfolio_snapshot(
            user_id=user_id,
            trigger=trigger,
            force_refresh=force_refresh,
        )

    async def get_holdings(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> list[dict[str, Any]]:
        snapshot = await self.get_portfolio(
            user_id=user_id,
            trigger=trigger,
            force_refresh=force_refresh,
        )
        return list(snapshot["holdings"])

    async def get_positions(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> list[dict[str, Any]]:
        snapshot = await self.get_portfolio(
            user_id=user_id,
            trigger=trigger,
            force_refresh=force_refresh,
        )
        return list(snapshot["positions"])

    async def get_funds(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> dict[str, Any]:
        snapshot = await self.get_portfolio(
            user_id=user_id,
            trigger=trigger,
            force_refresh=force_refresh,
        )
        return dict(snapshot["funds"])

    async def refresh_token(self, *, user_id: str, force: bool = False) -> str:
        return await self.broker_session_service.refresh_token_if_needed(
            user_id=user_id,
            broker=self.broker_name,
            force=force,
        )
