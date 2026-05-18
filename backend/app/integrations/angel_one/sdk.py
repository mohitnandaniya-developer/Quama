"""Shared Angel One SDK helpers used by auth, portfolio, and market workers."""

from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings
from app.core.exceptions import (
    BrokerAuthError,
    BrokerNotConfiguredError,
    BrokerRefreshError,
    BrokerTotpError,
)


def ensure_angel_one_configured(settings: Settings) -> None:
    """Fail fast when Angel One credentials are unavailable."""
    if not settings.angel_one_api_key.strip():
        raise BrokerNotConfiguredError(
            "ANGEL_ONE_API_KEY is required for Angel One integration."
        )
    if not settings.angel_one_secret_key.strip():
        raise BrokerNotConfiguredError(
            "ANGEL_ONE_SECRET_KEY is required for Angel One integration."
        )


def create_smart_connect(settings: Settings):
    """Create a SmartConnect REST client."""
    from SmartApi import SmartConnect

    return SmartConnect(api_key=settings.angel_one_api_key)


def create_market_feed_client(
    *,
    settings: Settings,
    auth_token: str,
    client_code: str,
    feed_token: str,
):
    """Create an Angel One market-feed websocket client."""
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2

    return SmartWebSocketV2(
        auth_token=auth_token,
        api_key=settings.angel_one_api_key,
        client_code=client_code,
        feed_token=feed_token,
    )


def bind_jwt_to_client(*, client: Any, jwt_token: str) -> None:
    """Attach a JWT to the SmartConnect client in the shape its SDK expects."""
    token_to_use = jwt_token[7:] if jwt_token.startswith("Bearer ") else jwt_token
    client.jwtToken = token_to_use
    if hasattr(client, "access_token"):
        client.access_token = token_to_use
    if hasattr(client, "setAccessToken"):
        client.setAccessToken(token_to_use)


def extract_response_data(payload: Any) -> dict[str, Any]:
    """Return the data mapping from an Angel One response payload."""
    if isinstance(payload, dict):
        if payload.get("status") is False:
            msg = payload.get("message", "Broker authentication failed.")
            raise BrokerAuthError(str(msg))
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return payload

    raise BrokerAuthError("Unexpected broker response shape.")


def extract_required_string(
    payload: dict[str, Any],
    keys: tuple[str, ...],
    *,
    fallback: str,
) -> str:
    """Extract a required string field from a response payload."""
    value = extract_optional_string(payload, keys)
    if not value:
        raise BrokerAuthError(f"Broker response did not include {fallback}.")
    return value


def extract_optional_string(
    payload: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    """Extract an optional string field from a response payload."""
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def normalize_sequence_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize an Angel One list-like payload into a list of mappings."""
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def normalize_mapping_payload(payload: Any) -> dict[str, Any]:
    """Normalize an Angel One mapping payload into a mapping."""
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        return data
    if isinstance(payload, dict):
        return payload
    return {}


def is_invalid_token_payload(payload: Any) -> bool:
    """Return whether Angel One rejected the request because the JWT is invalid."""
    if not isinstance(payload, dict):
        return False
    message = str(payload.get("message", "")).lower()
    error_code = str(payload.get("errorCode", "")).upper()
    return "invalid token" in message or error_code == "AG8001"


def raise_if_broker_payload_failed(payload: Any, *, fn_name: str) -> None:
    """Raise a normalized broker error if the payload reports failure."""
    if not isinstance(payload, dict):
        return
    if payload.get("status") is False or payload.get("success") is False:
        message = str(payload.get("message") or f"Broker request failed for {fn_name}.")
        raise BrokerRefreshError(message)


def map_broker_auth_error(exc: Exception) -> BrokerAuthError:
    """Map raw SDK exceptions into domain errors."""
    message = str(exc).lower()
    if "totp" in message or "otp" in message:
        return BrokerTotpError()
    return BrokerAuthError()


async def execute_read_call(*, client: Any, fn_name: str, **kwargs) -> Any:
    """Run a SmartConnect read call in a worker thread."""
    fn = getattr(client, fn_name)
    try:
        return await asyncio.to_thread(fn, **kwargs)
    except Exception as exc:  # pragma: no cover - depends on SDK/network.
        raise BrokerRefreshError(f"Broker request failed for {fn_name}.") from exc
