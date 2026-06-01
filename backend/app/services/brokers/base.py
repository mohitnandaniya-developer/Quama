"""Broker abstraction for user-scoped broker operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.broker import BrokerConnectResponse


class BaseBrokerService(ABC):
    """Abstract interface that every broker adapter must implement."""

    broker_name: str

    @abstractmethod
    async def connect(
        self,
        *,
        user_id: str,
        client_code: str,
        password: str,
        totp: str,
    ) -> BrokerConnectResponse:
        """Authenticate and persist an active broker session."""

    @abstractmethod
    async def disconnect(self, *, user_id: str) -> None:
        """Disconnect the active broker session."""

    @abstractmethod
    async def get_portfolio(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> dict[str, Any]:
        """Return the normalized portfolio snapshot."""

    @abstractmethod
    async def get_holdings(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> list[dict[str, Any]]:
        """Return current holdings."""

    @abstractmethod
    async def get_positions(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> list[dict[str, Any]]:
        """Return current positions."""

    @abstractmethod
    async def get_funds(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool,
    ) -> dict[str, Any]:
        """Return current funds and limits."""

    @abstractmethod
    async def refresh_token(self, *, user_id: str, force: bool = False) -> str:
        """Refresh and return a broker JWT/access token."""
