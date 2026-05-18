"""Groww implementation of the broker abstraction."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.exceptions import (
    BrokerAuthError,
    BrokerSessionNotFoundError,
    PortfolioSyncError,
)
from app.schemas.broker import BrokerConnectResponse
from app.services.broker_session_service import GROWW_BROKER, BrokerSessionService
from app.services.brokers.base import BaseBrokerService
from app.services.portfolio_sync_service import PortfolioSyncService

logger = logging.getLogger(__name__)
GROWW_LTP_BATCH_SIZE = 50

SYMBOL_KEYS = (
    "trading_symbol",
    "tradingSymbol",
    "tradingsymbol",
    "groww_symbol",
    "growwSymbol",
    "symbol",
    "nse_symbol",
    "nseSymbol",
    "name",
    "scrip",
)
QUANTITY_KEYS = (
    "quantity",
    "qty",
    "holding_quantity",
    "holdingQuantity",
    "holdingquantity",
    "total_quantity",
    "totalQuantity",
    "totalquantity",
    "free_quantity",
    "freeQuantity",
    "freequantity",
)
AVERAGE_PRICE_KEYS = (
    "average_price",
    "averagePrice",
    "averageprice",
    "average_buy_price",
    "averageBuyPrice",
    "averagebuyprice",
    "avg_price",
    "avgPrice",
    "avgprice",
    "avg_buy_price",
    "avgBuyPrice",
    "avgbuyprice",
    "buy_price",
    "buyPrice",
    "buyprice",
    "cost_price",
    "costPrice",
    "costprice",
)
LTP_KEYS = (
    "ltp",
    "last_price",
    "lastPrice",
    "lastprice",
    "close",
    "close_price",
    "closePrice",
    "closeprice",
)
CURRENT_VALUE_KEYS = (
    "current_value",
    "currentValue",
    "currentvalue",
    "market_value",
    "marketValue",
    "marketvalue",
    "ltp_value",
    "ltpValue",
    "ltpvalue",
)
INVESTED_VALUE_KEYS = (
    "invested",
    "invested_amount",
    "investedAmount",
    "investedamount",
    "investment_amount",
    "investmentAmount",
    "investmentamount",
    "total_investment",
    "totalInvestment",
    "totalinvestment",
    "buy_amount",
    "buyAmount",
    "buyamount",
    "bought_value",
    "boughtValue",
    "boughtvalue",
    # Groww uses holdingValue for current market value, not invested cost.
)
PNL_KEYS = (
    "pnl",
    "profit_and_loss",
    "profitAndLoss",
    "profitandloss",
    "unrealised_pnl",
    "unrealisedPnl",
    "unrealisedPnL",
    "unrealisedpnl",
    "unrealized_pnl",
    "unrealizedPnl",
    "unrealizedPnL",
    "unrealizedpnl",
    "gain_loss",
    "gainLoss",
    "gainloss",
    "m2m",
)
PNL_PERCENT_KEYS = (
    "pnl_percentage",
    "pnlPercentage",
    "pnlpercentage",
    "profit_loss_percentage",
    "profitLossPercentage",
    "profitlosspercentage",
    "gain_loss_percentage",
    "gainLossPercentage",
    "gainlosspercentage",
)
SECTOR_KEYS = (
    "sector",
    "industry",
    "asset_class",
    "assetClass",
    "assetclass",
    "category",
)
EXCHANGE_KEYS = (
    "exchange",
    "stock_exchange",
    "stockExchange",
    "stockexchange",
)


class GrowwBrokerService(BaseBrokerService):
    """Broker adapter for Groww Trading API."""

    broker_name = GROWW_BROKER

    def __init__(
        self,
        *,
        broker_session_service: BrokerSessionService,
    ) -> None:
        self.broker_session_service = broker_session_service

    async def connect(
        self,
        *,
        user_id: str,
        client_code: str,
        password: str,
        totp: str,
    ) -> BrokerConnectResponse:
        del password
        return await self.broker_session_service.connect_groww(
            user_id=user_id,
            api_key=client_code,
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
        """Return a normalized Groww portfolio snapshot."""
        del force_refresh
        holdings = await self.get_holdings(user_id=user_id, trigger=trigger)
        positions = await self.get_positions(user_id=user_id, trigger=trigger)
        funds = await self.get_funds(user_id=user_id, trigger=trigger)
        performance_history = await self._build_performance_history(
            user_id=user_id,
            holdings=holdings,
        )

        now = datetime.now(UTC).isoformat()
        return {
            "user_id": user_id,
            "broker": self.broker_name,
            "trigger": trigger,
            "synced_at": now,
            "holdings": holdings,
            "positions": positions,
            "funds": funds,
            "performance_history": performance_history,
            "summary": PortfolioSyncService._build_portfolio_totals(
                holdings=holdings,
                positions=positions,
                funds=funds,
            ),
        }

    async def get_holdings(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return current Groww holdings."""
        del trigger, force_refresh
        payload = await self._request_groww_json(
            user_id=user_id,
            path="/holdings/user",
            operation="holdings",
        )
        raw_holdings = self._extract_payload_list(payload, "holdings")
        ltp_by_symbol = await self._fetch_ltp_map(
            user_id=user_id,
            holdings=raw_holdings,
        )
        return [
            self._normalize_holding(row, ltp_by_symbol=ltp_by_symbol)
            for row in raw_holdings
        ]

    async def get_positions(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return current Groww positions."""
        del trigger, force_refresh
        payload = await self._request_groww_json(
            user_id=user_id,
            path="/positions/user",
            operation="positions",
        )
        return self._extract_payload_list(payload, "positions")

    async def get_funds(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return current Groww margin and cash details."""
        del trigger, force_refresh
        payload = await self._request_groww_json(
            user_id=user_id,
            path="/margins/detail/user",
            operation="margin",
        )
        inner = payload.get("payload")
        funds = inner if isinstance(inner, dict) else payload

        normalized: dict[str, Any] = dict(funds)

        # Groww may expose cash either at top level or inside margin details.
        available_cash = None
        if "clear_cash" in normalized:
            available_cash = self._parse_number(normalized["clear_cash"])
        elif isinstance(normalized.get("equity_margin_details"), dict):
            margin_details = normalized["equity_margin_details"]
            available_cash = self._parse_number(
                margin_details.get("cnc_balance_available")
            )

        if available_cash is not None:
            normalized["availablecash"] = available_cash

        return normalized

    async def refresh_token(self, *, user_id: str, force: bool = False) -> str:
        del user_id, force
        raise BrokerSessionNotFoundError(
            "Groww sessions require a fresh TOTP login. Please reconnect Groww."
        )

    async def validate_session(self, *, user_id: str) -> bool:
        session = await self.broker_session_service.get_active_session(
            user_id=user_id,
            broker=self.broker_name,
        )
        return session is not None

    async def _request_groww_json(
        self,
        *,
        user_id: str,
        path: str,
        operation: str,
    ) -> dict[str, Any]:
        token = await self.broker_session_service.get_jwt(
            user_id=user_id,
            broker=self.broker_name,
        )
        client = self._create_groww_client(token)
        try:
            if path == "/holdings/user":
                payload = await asyncio.to_thread(
                    client.get_holdings_for_user,
                    timeout=5,
                )
            elif path == "/positions/user":
                payload = await asyncio.to_thread(client.get_positions_for_user)
            elif path == "/margins/detail/user":
                payload = await asyncio.to_thread(client.get_available_margin_details)
            else:
                raise PortfolioSyncError(f"Unsupported Groww {operation} request.")
        except (BrokerAuthError, PortfolioSyncError):
            raise
        except Exception as exc:
            if self._is_auth_error(exc):
                await self.broker_session_service.invalidate_session(
                    user_id=user_id,
                    broker=self.broker_name,
                )
                raise BrokerSessionNotFoundError(
                    "Groww session expired. Please reconnect Groww."
                ) from exc
            raise PortfolioSyncError(f"Groww {operation} request failed.") from exc

        if not isinstance(payload, dict):
            raise PortfolioSyncError(f"Groww {operation} response was invalid.")
        if payload.get("status") == "FAILURE":
            message = self._extract_error_message(payload)
            if "token" in message.lower() or "auth" in message.lower():
                await self.broker_session_service.invalidate_session(
                    user_id=user_id,
                    broker=self.broker_name,
                )
                raise BrokerSessionNotFoundError(
                    "Groww session expired. Please reconnect Groww."
                )
            raise BrokerAuthError(message or f"Groww {operation} request failed.")
        return payload

    def _create_groww_client(self, access_token: str) -> Any:
        groww_api = BrokerSessionService._get_groww_api_class()
        return groww_api(access_token)

    async def _fetch_ltp_map(
        self,
        *,
        user_id: str,
        holdings: list[dict[str, Any]],
    ) -> dict[str, float]:
        exchange_symbols: list[str] = []
        for holding in holdings:
            exchange_symbol = self._exchange_symbol_for_holding(holding)
            if exchange_symbol and exchange_symbol not in exchange_symbols:
                exchange_symbols.append(exchange_symbol)

        if not exchange_symbols:
            return {}

        token = await self.broker_session_service.get_jwt(
            user_id=user_id,
            broker=self.broker_name,
        )
        client = self._create_groww_client(token)
        values: dict[str, float] = {}

        for start in range(0, len(exchange_symbols), GROWW_LTP_BATCH_SIZE):
            batch = tuple(exchange_symbols[start : start + GROWW_LTP_BATCH_SIZE])
            missing_symbols = list(batch)
            try:
                payload = await asyncio.to_thread(
                    client.get_ltp,
                    batch,
                    "CASH",
                    timeout=5,
                )
            except Exception as exc:
                logger.warning(
                    "Groww LTP batch fetch failed for %s symbols; "
                    "retrying individually: %s",
                    len(batch),
                    exc,
                )
            else:
                batch_values = self._extract_ltp_map(payload)
                values.update(batch_values)
                missing_symbols = [
                    symbol
                    for symbol in batch
                    if self._lookup_ltp(batch_values, symbol) is None
                ]

            for symbol in missing_symbols:
                try:
                    payload = await asyncio.to_thread(
                        client.get_ltp,
                        (symbol,),
                        "CASH",
                        timeout=5,
                    )
                except Exception as exc:
                    logger.warning("Groww LTP fetch failed for %s: %s", symbol, exc)
                    continue
                values.update(self._extract_ltp_map(payload))

        missing_symbols = [
            symbol
            for symbol in exchange_symbols
            if self._lookup_ltp(values, symbol) is None
        ]
        if missing_symbols:
            quote_values = await self._fetch_quote_ltp_map(
                client=client,
                holdings=holdings,
                missing_exchange_symbols=missing_symbols,
            )
            values.update(quote_values)

        return values

    async def _fetch_quote_ltp_map(
        self,
        *,
        client: Any,
        holdings: list[dict[str, Any]],
        missing_exchange_symbols: list[str],
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        missing_lookup = set(missing_exchange_symbols)

        for holding in holdings:
            exchange_symbol = self._exchange_symbol_for_holding(holding)
            if exchange_symbol not in missing_lookup:
                continue

            trading_symbol = self._groww_symbol_for_holding(holding)
            if not trading_symbol:
                continue

            exchange = self._exchange_for_holding(holding)
            try:
                payload = await asyncio.to_thread(
                    client.get_quote,
                    trading_symbol,
                    exchange,
                    "CASH",
                    timeout=5,
                )
            except Exception as exc:
                logger.warning(
                    "Groww quote fetch failed for %s_%s: %s",
                    exchange,
                    trading_symbol,
                    exc,
                )
                continue

            quote_ltp = self._extract_quote_ltp(payload)
            if quote_ltp is None:
                continue
            for lookup_key in self._symbol_lookup_keys(exchange_symbol):
                values[lookup_key] = quote_ltp
            for lookup_key in self._symbol_lookup_keys(trading_symbol):
                values[lookup_key] = quote_ltp

        return values

    async def get_history(self, user_id: str, period: str) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        end_at = now

        if period == "1h" or period == "1H":
            interval_str = "5m"
            start_at = end_at - timedelta(hours=1)
        elif period == "1d" or period == "1D":
            interval_str = "15m"
            start_at = end_at - timedelta(days=1)
        elif period == "1m" or period == "1M":
            interval_str = "1day"
            start_at = end_at - timedelta(days=30)
        else:
            interval_str = "1day"
            start_at = end_at - timedelta(days=365)

        holdings_payload = await self.get_portfolio(
            user_id=user_id,
            trigger="user_action",
        )
        holdings = holdings_payload.get("holdings", [])
        if not holdings:
            return []

        total_invested = 0.0
        for h in holdings:
            qty = self._pick_number(h, QUANTITY_KEYS) or 0.0
            avg = (
                self._pick_number(
                    h,
                    ["average_price", "averagePrice", "avg_price", "costPrice"],
                )
                or 0.0
            )
            total_invested += qty * avg

        weighted_history: dict[str, float] = {}
        token = await self.broker_session_service.get_jwt(
            user_id=user_id,
            broker=self.broker_name,
        )
        client = self._create_groww_client(token)
        semaphore = asyncio.Semaphore(4)

        async def fetch_holding_history(
            holding: dict[str, Any],
        ) -> tuple[float, Any] | None:
            quantity = self._pick_number(holding, QUANTITY_KEYS) or 0.0
            if quantity <= 0:
                return None

            groww_symbol = self._groww_symbol_for_holding(holding)
            if not groww_symbol:
                return None

            try:
                async with semaphore:
                    payload = await asyncio.to_thread(
                        client.get_historical_candles,
                        "NSE",
                        "CASH",
                        groww_symbol,
                        start_at.strftime("%Y-%m-%d %H:%M:%S"),
                        end_at.strftime("%Y-%m-%d %H:%M:%S"),
                        interval_str,
                        timeout=5,
                    )
            except Exception:
                return None
            return quantity, payload

        history_payloads = await asyncio.gather(
            *(fetch_holding_history(holding) for holding in holdings)
        )

        for result in history_payloads:
            if result is None:
                continue
            quantity, payload = result
            for candle in self._extract_candles(payload):
                candle_date = candle.get("date")
                close = PortfolioSyncService._parse_numeric_value(candle.get("close"))
                if not candle_date or close is None:
                    continue

                ts = candle.get("time") or candle.get("timestamp") or candle_date

                weighted_history[str(ts)] = weighted_history.get(str(ts), 0.0) + (
                    close * quantity
                )

        return [
            {
                "date": str(ts),
                "value": round(value, 2),
                "invested": round(total_invested, 2),
            }
            for ts, value in sorted(weighted_history.items())
        ]

    async def _build_performance_history(
        self,
        *,
        user_id: str,
        holdings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not holdings:
            return []

        weighted_history: dict[str, float] = {}
        end_at = datetime.now(UTC)
        start_at = end_at - timedelta(days=365)
        token = await self.broker_session_service.get_jwt(
            user_id=user_id,
            broker=self.broker_name,
        )
        client = self._create_groww_client(token)
        semaphore = asyncio.Semaphore(4)

        async def fetch_holding_history(
            holding: dict[str, Any],
        ) -> tuple[float, Any] | None:
            quantity = self._pick_number(holding, QUANTITY_KEYS) or 0.0
            if quantity <= 0:
                return None

            groww_symbol = self._groww_symbol_for_holding(holding)
            if not groww_symbol:
                return None

            try:
                async with semaphore:
                    payload = await asyncio.to_thread(
                        client.get_historical_candles,
                        "NSE",
                        "CASH",
                        groww_symbol,
                        start_at.strftime("%Y-%m-%d %H:%M:%S"),
                        end_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "1day",
                        timeout=5,
                    )
            except Exception:
                return None
            return quantity, payload

        history_payloads = await asyncio.gather(
            *(fetch_holding_history(holding) for holding in holdings)
        )
        for result in history_payloads:
            if result is None:
                continue
            quantity, payload = result
            for candle in self._extract_candles(payload):
                candle_date = candle.get("date")
                close = PortfolioSyncService._parse_numeric_value(candle.get("close"))
                if not candle_date or close is None:
                    continue
                weighted_history[candle_date] = weighted_history.get(
                    candle_date, 0.0
                ) + (close * quantity)

        if not weighted_history and holdings:
            current_total = sum(
                PortfolioSyncService._parse_numeric_value(holding.get("current_value"))
                or 0.0
                for holding in holdings
            )
            if current_total > 0:
                weighted_history[end_at.date().isoformat()] = current_total

        current_total = sum(
            PortfolioSyncService._parse_numeric_value(holding.get("current_value"))
            or 0.0
            for holding in holdings
        )
        today_key = end_at.date().isoformat()
        if current_total > 0:
            weighted_history[today_key] = current_total

        return [
            {
                "date": day,
                "value": round(value, 2),
            }
            for day, value in sorted(weighted_history.items())
        ]

    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(
            term in message
            for term in (
                "401",
                "403",
                "unauthorized",
                "forbidden",
                "invalid token",
                "token expired",
            )
        )

    @staticmethod
    def _extract_payload_list(
        payload: dict[str, Any],
        key: str,
    ) -> list[dict[str, Any]]:
        inner = payload.get("payload")
        source = inner if isinstance(inner, dict) else payload
        rows = source.get(key)
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    @classmethod
    def _normalize_holding(
        cls,
        holding: dict[str, Any],
        *,
        ltp_by_symbol: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(holding)
        symbol = cls._pick_string(normalized, SYMBOL_KEYS)
        quantity = cls._pick_number(normalized, QUANTITY_KEYS) or 0.0
        average_price = cls._pick_number(normalized, AVERAGE_PRICE_KEYS) or 0.0
        ltp = cls._pick_number(normalized, LTP_KEYS)
        live_ltp = cls._lookup_ltp(ltp_by_symbol or {}, symbol)

        # Use live LTP if available, otherwise use extracted LTP
        effective_ltp = live_ltp if live_ltp is not None else ltp

        invested_value = cls._pick_number(normalized, INVESTED_VALUE_KEYS)
        current_value = cls._pick_number(normalized, CURRENT_VALUE_KEYS)
        pnl = cls._pick_number(normalized, PNL_KEYS)
        pnl_percentage = cls._pick_number(normalized, PNL_PERCENT_KEYS)
        sector = cls._pick_string(normalized, SECTOR_KEYS)

        # Smart average price resolution:
        # If API provides average_price, use it.
        # Otherwise, try to compute from invested_value,
        # but only if invested_value is original cost (not current market value)
        if average_price > 0 and quantity > 0:
            # We have average_price from API, trust it
            if invested_value is None or invested_value <= 0:
                invested_value = quantity * average_price
        elif invested_value is not None and invested_value > 0 and quantity > 0:
            computed_avg = invested_value / quantity
            # Check if this looks like the original cost (not current market value)
            if effective_ltp is None or abs(computed_avg - effective_ltp) > 0.01:
                average_price = computed_avg
            # If they're very close, invested_value is likely current market value
            # In this case, we can't determine original cost, so mark as unreliable

        # Final fallback for invested_value
        if invested_value is None or invested_value <= 0:
            if quantity > 0 and average_price > 0:
                invested_value = quantity * average_price
            else:
                invested_value = 0.0

        # Ensure current_value is set using effective_ltp
        if current_value is None or current_value <= 0:
            if effective_ltp is not None and effective_ltp > 0:
                current_value = quantity * effective_ltp
            elif average_price > 0 and quantity > 0:
                current_value = quantity * average_price
            else:
                current_value = 0.0

        # Resolve LTP from current_value if needed
        if effective_ltp is None or effective_ltp <= 0:
            effective_ltp = current_value / quantity if quantity > 0 else average_price

        # Compute PnL if not provided
        if pnl is None:
            pnl = current_value - invested_value

        # Compute PnL percentage if not provided
        if pnl_percentage is None:
            if invested_value > 0:
                pnl_percentage = (pnl / invested_value) * 100
            else:
                pnl_percentage = 0.0

        normalized.update(
            {
                "symbol": symbol or "Groww holding",
                "quantity": quantity,
                "average_price": average_price,
                "ltp": effective_ltp,
                "invested_amount": invested_value,
                "current_value": current_value,
                "pnl": pnl,
                "pnl_percentage": pnl_percentage,
                # Also add camelCase variants for frontend compatibility
                "investedAmount": invested_value,
                "currentValue": current_value,
                "pnlPercentage": pnl_percentage,
            }
        )
        if sector:
            normalized["sector"] = sector
        return normalized

    @staticmethod
    def _extract_error_message(payload: dict[str, Any]) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
        message = payload.get("message")
        return message if isinstance(message, str) else ""

    @staticmethod
    def _pick_string(source: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        canonical_values = {
            GrowwBrokerService._canonical_field_name(key): value
            for key, value in source.items()
        }
        for key in keys:
            value = source.get(key)
            if value is None:
                value = canonical_values.get(
                    GrowwBrokerService._canonical_field_name(key)
                )
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _pick_number(source: dict[str, Any], keys: tuple[str, ...]) -> float | None:
        canonical_values = {
            GrowwBrokerService._canonical_field_name(key): value
            for key, value in source.items()
        }
        for key in keys:
            raw_value = source.get(key)
            if raw_value is None:
                raw_value = canonical_values.get(
                    GrowwBrokerService._canonical_field_name(key)
                )
            value = GrowwBrokerService._parse_number(raw_value)
            if value is not None:
                return value
        return None

    @staticmethod
    def _parse_number(value: Any) -> float | None:
        if isinstance(value, str):
            value = value.replace("%", "")
        return PortfolioSyncService._parse_numeric_value(value)

    @staticmethod
    def _canonical_field_name(value: str) -> str:
        return "".join(char.lower() for char in value if char.isalnum())

    @classmethod
    def _exchange_symbol_for_holding(cls, holding: dict[str, Any]) -> str | None:
        explicit = cls._pick_string(
            holding,
            (
                "exchange_symbol",
                "exchangeSymbol",
                "exchange_trading_symbol",
                "exchangeTradingSymbol",
            ),
        )
        if explicit:
            return explicit.replace(":", "_").upper()

        symbol = cls._pick_string(holding, SYMBOL_KEYS)
        if not symbol:
            return None
        normalized = cls._normalize_symbol_key(symbol)
        if not normalized:
            return None
        if normalized.startswith(("NSE_", "BSE_")):
            return normalized
        exchange = cls._exchange_for_holding(holding)
        return f"{exchange}_{normalized}"

    @classmethod
    def _groww_symbol_for_holding(cls, holding: dict[str, Any]) -> str | None:
        symbol = cls._pick_string(holding, ("groww_symbol", "growwSymbol"))
        if symbol:
            return symbol.strip().upper()
        symbol = cls._pick_string(holding, SYMBOL_KEYS)
        if not symbol:
            return None
        return cls._normalize_symbol_key(symbol).removeprefix("NSE_")

    @classmethod
    def _exchange_for_holding(cls, holding: dict[str, Any]) -> str:
        exchange = cls._pick_string(holding, EXCHANGE_KEYS)
        if exchange:
            normalized = exchange.strip().upper()
            if normalized in {"NSE", "BSE"}:
                return normalized
        return "NSE"

    @classmethod
    def _lookup_ltp(
        cls,
        ltp_by_symbol: dict[str, float],
        symbol: str | None,
    ) -> float | None:
        if not symbol:
            return None
        for key in cls._symbol_lookup_keys(symbol):
            value = ltp_by_symbol.get(key)
            if value is not None:
                return value
        return None

    @classmethod
    def _extract_ltp_map(cls, payload: Any) -> dict[str, float]:
        values: dict[str, float] = {}
        source = (
            payload.get("payload", payload) if isinstance(payload, dict) else payload
        )

        def store(symbol: Any, value: Any) -> None:
            if not isinstance(symbol, str) or not symbol.strip():
                return
            ltp = cls._parse_number(value)
            if ltp is None:
                return
            for lookup_key in cls._symbol_lookup_keys(symbol):
                values[lookup_key] = ltp

        if isinstance(source, dict):
            rows = source.get("ltp")
            if isinstance(rows, dict):
                source = rows

        if isinstance(source, dict):
            for symbol, value in source.items():
                if isinstance(value, dict):
                    store(
                        value.get("trading_symbol")
                        or value.get("tradingSymbol")
                        or value.get("symbol")
                        or symbol,
                        cls._pick_number(value, LTP_KEYS),
                    )
                else:
                    store(symbol, value)
        elif isinstance(source, list):
            for row in source:
                if not isinstance(row, dict):
                    continue
                store(
                    cls._pick_string(row, SYMBOL_KEYS),
                    cls._pick_number(row, LTP_KEYS),
                )

        return values

    @classmethod
    def _extract_quote_ltp(cls, payload: Any) -> float | None:
        source = payload.get("payload") if isinstance(payload, dict) else payload
        if not isinstance(source, dict):
            return None
        return cls._pick_number(
            source,
            (
                "last_price",
                "lastPrice",
                "lastprice",
                "ltp",
                "close",
                "close_price",
                "closePrice",
                "closeprice",
            ),
        )

    @classmethod
    def _symbol_lookup_keys(cls, symbol: str) -> tuple[str, ...]:
        normalized = cls._normalize_symbol_key(symbol)
        without_exchange = normalized
        if "_" in without_exchange:
            maybe_exchange, maybe_symbol = without_exchange.split("_", 1)
            if maybe_exchange in {"NSE", "BSE"}:
                without_exchange = maybe_symbol
        return tuple(
            key
            for key in (
                symbol.strip().upper(),
                normalized,
                without_exchange,
                f"NSE_{without_exchange}",
                f"NSE:{without_exchange}",
            )
            if key
        )

    @staticmethod
    def _to_colon_format(symbol: str) -> str:
        """Convert NSE_RELIANCE to NSE:RELIANCE for Groww API calls.

        Only replaces the first underscore when the prefix is a known exchange
        (NSE or BSE). Returns the symbol unchanged if it already uses colon
        format or has no recognised exchange prefix.
        """
        for prefix in ("NSE_", "BSE_"):
            if symbol.startswith(prefix):
                return prefix[:-1] + ":" + symbol[len(prefix) :]
        return symbol

    @staticmethod
    def _normalize_symbol_key(symbol: str) -> str:
        normalized = symbol.strip().upper().replace(":", "_").replace(" ", "")
        if normalized.endswith("-EQ"):
            normalized = normalized[:-3]
        if normalized.endswith("_EQ"):
            normalized = normalized[:-3]
        return normalized

    @classmethod
    def _extract_candles(cls, payload: Any) -> list[dict[str, Any]]:
        source = payload.get("payload") if isinstance(payload, dict) else payload
        if isinstance(source, dict):
            for key in ("candles", "data"):
                inner = source.get(key)
                if isinstance(inner, dict) and isinstance(inner.get("candles"), list):
                    source = inner.get("candles")
                    break
                if isinstance(inner, list):
                    source = inner
                    break

        if not isinstance(source, list):
            return []

        candles: list[dict[str, Any]] = []
        for row in source:
            if isinstance(row, dict):
                date_value = (
                    row.get("date")
                    or row.get("timestamp")
                    or row.get("time")
                    or row.get("start_time")
                    or row.get("startTime")
                )
                close = (
                    row.get("close")
                    or row.get("close_price")
                    or row.get("closePrice")
                    or row.get("c")
                )
            elif isinstance(row, (list, tuple)) and len(row) >= 5:
                date_value = row[0]
                close = row[4]
            else:
                continue

            candle_date = cls._format_candle_date(date_value)
            if candle_date:
                candles.append({"date": candle_date, "close": close})
        return candles

    @staticmethod
    def _format_candle_date(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, (int, float)):
            timestamp = value / 1000 if value > 10_000_000_000 else value
            return datetime.fromtimestamp(timestamp, UTC).date().isoformat()
        if isinstance(value, str) and value.strip():
            raw_value = value.strip()
            try:
                return (
                    datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
                    .date()
                    .isoformat()
                )
            except ValueError:
                return raw_value[:10]
        return None
