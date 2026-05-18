"""Broker registry tests for multi-broker routing readiness."""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidBrokerError
from app.services.brokers.registry import BrokerServiceRegistry


class _StubBrokerService:
    """Simple broker stub for registry behavior tests."""

    def __init__(self, name: str) -> None:
        self.broker_name = name


def test_registry_resolves_default_broker() -> None:
    registry = BrokerServiceRegistry(
        services={"angel_one": _StubBrokerService("angel_one")},
        default_broker="angel_one",
    )

    service = registry.get()

    assert service.broker_name == "angel_one"


def test_registry_normalizes_hyphenated_broker_name() -> None:
    registry = BrokerServiceRegistry(
        services={"angel_one": _StubBrokerService("angel_one")},
        default_broker="angel_one",
    )

    service = registry.get("angel-one")

    assert service.broker_name == "angel_one"


def test_registry_rejects_unknown_broker() -> None:
    registry = BrokerServiceRegistry(
        services={"angel_one": _StubBrokerService("angel_one")},
        default_broker="angel_one",
    )

    with pytest.raises(InvalidBrokerError, match="Unsupported broker"):
        registry.get("kite")
