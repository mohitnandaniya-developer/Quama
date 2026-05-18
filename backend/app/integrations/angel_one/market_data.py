"""Angel One market-data normalization helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def group_instruments_by_exchange(
    instruments: list[dict[str, int | str]],
) -> list[dict[str, object]]:
    """Group instrument tokens into the SmartWebSocketV2 tokenList shape."""
    grouped: dict[int, list[str]] = {}
    for instrument in instruments:
        exchange_type = int(instrument["exchange_type"])
        instrument_token = str(instrument["instrument_token"]).strip()
        grouped.setdefault(exchange_type, []).append(instrument_token)
    return [
        {"exchangeType": exchange_type, "tokens": sorted(set(tokens))}
        for exchange_type, tokens in sorted(grouped.items())
    ]


def normalize_tick(
    payload: dict[str, Any],
    *,
    price_scale: float,
) -> dict[str, Any]:
    """Normalize an Angel One websocket tick into a stable payload."""
    instrument_token = str(payload.get("token", "")).strip()
    exchange_type = _parse_int(payload.get("exchange_type"))
    price_raw = _parse_float(payload.get("last_traded_price"))
    volume = _parse_float(
        payload.get("volume_trade_for_the_day") or payload.get("last_traded_quantity")
    )
    exchange_timestamp = _parse_timestamp(payload.get("exchange_timestamp"))

    normalized_price = None
    if price_raw is not None:
        normalized_price = price_raw / price_scale if price_scale else price_raw

    return {
        "instrument_token": instrument_token,
        "exchange_type": exchange_type,
        "subscription_mode": _parse_int(payload.get("subscription_mode")),
        "sequence_number": _parse_int(payload.get("sequence_number")),
        "price": normalized_price,
        "price_raw": price_raw,
        "volume": volume,
        "timestamp": exchange_timestamp.isoformat() if exchange_timestamp else None,
        "source": "angel_one",
        "published_at": datetime.now(UTC).isoformat(),
    }


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _parse_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    parsed = _parse_int(value)
    if parsed is None or parsed <= 0:
        return None
    divisor = 1000 if parsed > 10_000_000_000 else 1
    try:
        return datetime.fromtimestamp(parsed / divisor, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
