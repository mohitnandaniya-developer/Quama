"""Broker registry used to resolve broker services dynamically."""

from __future__ import annotations

from app.core.exceptions import InvalidBrokerError
from app.services.brokers.base import BaseBrokerService


class BrokerServiceRegistry:
    """Map broker names to concrete broker service adapters."""

    def __init__(
        self,
        *,
        services: dict[str, BaseBrokerService],
        default_broker: str,
    ) -> None:
        if not services:
            raise InvalidBrokerError("At least one broker service must be registered.")

        self._services = {
            self._normalize_broker_name(name): service
            for name, service in services.items()
        }
        self._default_broker = self._normalize_broker_name(default_broker)
        if self._default_broker not in self._services:
            raise InvalidBrokerError(
                f"Default broker '{self._default_broker}' is not registered."
            )

    def get(self, broker: str | None = None) -> BaseBrokerService:
        """Return a broker service by broker id or the configured default."""
        broker_key = self._normalize_broker_name(broker or self._default_broker)
        service = self._services.get(broker_key)
        if service is None:
            raise InvalidBrokerError(f"Unsupported broker '{broker_key}'.")
        return service

    @staticmethod
    def _normalize_broker_name(value: str) -> str:
        normalized = value.strip().lower().replace("-", "_")
        if not normalized:
            raise InvalidBrokerError("Broker name is required.")
        return normalized
