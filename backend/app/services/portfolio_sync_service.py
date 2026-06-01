"""Portfolio sync pipeline for Angel One and Groww REST data."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.cache_keys import portfolio_snapshot_key
from app.core.exceptions import BrokerAuthError, BrokerSessionNotFoundError
from app.integrations.angel_one.sdk import (
    bind_jwt_to_client,
    create_smart_connect,
    ensure_angel_one_configured,
    execute_read_call,
    is_invalid_token_payload,
    normalize_mapping_payload,
    normalize_sequence_payload,
    raise_if_broker_payload_failed,
)
from app.models.broker_session import BrokerSession
from app.services.broker_session_service import (
    ANGEL_ONE_BROKER,
    GROWW_BROKER,
    BrokerSessionService,
)
from app.services.cache_service import CacheService
from app.services.portfolio_history import resolve_portfolio_history_window

logger = logging.getLogger(__name__)
PORTFOLIO_CACHE_SCHEMA = "quama.portfolio-snapshot.v1"


class PortfolioSyncService:
    """Own the REST-driven portfolio pipeline and its cache."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        cache_service: CacheService,
        settings: Settings,
        broker_session_service: BrokerSessionService,
    ) -> None:
        self.session = session
        self.cache_service = cache_service
        self.settings = settings
        self.broker_session_service = broker_session_service

    async def get_portfolio_snapshot(
        self,
        *,
        user_id: str,
        trigger: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Return the portfolio snapshot, using Redis as the primary cache."""
        cache_key = portfolio_snapshot_key(user_id=user_id)
        broker_session = await self.broker_session_service.get_active_session(
            user_id=user_id,
            broker=ANGEL_ONE_BROKER,
        )
        if broker_session is None:
            await self.cache_service.delete(cache_key)
            raise BrokerSessionNotFoundError()

        cache_version = self._cache_version(broker_session)
        if not force_refresh:
            cached = await self.cache_service.get(cache_key)
            cached_snapshot = self._extract_cached_snapshot(
                cached=cached,
                cache_version=cache_version,
            )
            if cached_snapshot is not None:
                return cached_snapshot
            if cached is not None:
                await self.cache_service.delete(cache_key)

        snapshot = await self._fetch_portfolio_snapshot(
            user_id=user_id,
            trigger=trigger,
        )
        await self.cache_service.set(
            cache_key,
            self._cache_record(snapshot=snapshot, cache_version=cache_version),
            self.settings.portfolio_cache_ttl_seconds,
        )
        return snapshot

    async def get_portfolio_history(
        self, user_id: str, broker: str, period: str
    ) -> list[dict[str, Any]]:
        """Fetch historical performance data for the requested period."""
        broker_key = broker.strip().lower().replace("-", "_")
        logger.info(
            "get_portfolio_history called for user %s broker %s period %s",
            user_id,
            broker_key,
            period,
        )

        if broker_key == GROWW_BROKER:
            from app.services.brokers.groww_service import GrowwBrokerService

            service = GrowwBrokerService(
                broker_session_service=self.broker_session_service,
            )
            try:
                history = await service.get_history(user_id=user_id, period=period)
                logger.info(
                    "Groww history returned %d data points for user %s period %s",
                    len(history),
                    user_id,
                    period,
                )
                return history
            except Exception as exc:
                logger.error(
                    "Groww history fetch failed for user %s period %s: %s",
                    user_id,
                    period,
                    exc,
                    exc_info=True,
                )
                raise

        if broker_key == ANGEL_ONE_BROKER:
            try:
                history = await self._build_angel_one_performance_history(
                    user_id=user_id, period=period
                )
                logger.info(
                    "Angel One history returned %d data points for user %s period %s",
                    len(history),
                    user_id,
                    period,
                )
                return history
            except Exception as exc:
                logger.error(
                    "Angel One history fetch failed for user %s period %s: %s",
                    user_id,
                    period,
                    exc,
                    exc_info=True,
                )
                raise

        logger.warning(
            "Unknown broker %s for user %s period %s",
            broker_key,
            user_id,
            period,
        )
        return []

    async def _build_angel_one_performance_history(
        self, user_id: str, period: str
    ) -> list[dict[str, Any]]:
        # Add delay to prevent racing with portfolio snapshot's holding() call
        await asyncio.sleep(0.5)
        holdings_payload = await self._call_angel_one(
            user_id=user_id,
            fn_name="holding",
        )
        holdings = self._extract_angel_one_holdings(holdings_payload)
        holdings = [self._normalize_angel_one_holding(h) for h in holdings]
        if not holdings:
            return []

        summary = self._build_portfolio_totals(
            holdings=holdings,
            positions=[],
            funds={},
        )
        total_invested = summary["investment"] or 0.0
        current_total = summary["holdings_market_value"] or 0.0

        window = resolve_portfolio_history_window(
            period,
            end_at=datetime.now(UTC),
        )
        end_time = window.end_at

        if window.period == "1H":
            interval = "ONE_MINUTE"
        elif window.period == "1D":
            interval = "FIVE_MINUTE"
        else:
            interval = "ONE_DAY"

        from_date = window.start_at.strftime("%Y-%m-%d %H:%M")
        to_date = end_time.strftime("%Y-%m-%d %H:%M")

        weighted_history: dict[str, float] = {}
        # Use semaphore of 1 to serialize getCandleData calls and avoid rate limiting
        semaphore = asyncio.Semaphore(1)

        async def fetch_holding_history(
            holding: dict[str, Any],
        ) -> tuple[float, Any] | None:
            quantity = holding.get("quantity", 0)
            if quantity <= 0:
                return None

            token = holding.get("symboltoken") or holding.get("symbolToken")
            exchange = holding.get("exchange", "NSE")
            if not token:
                return None

            try:
                params = {
                    "exchange": exchange,
                    "symboltoken": str(token),
                    "interval": interval,
                    "fromdate": from_date,
                    "todate": to_date,
                }
                async with semaphore:
                    # Add delay before each call to throttle requests
                    await asyncio.sleep(0.5)
                    payload = await self._call_angel_one(
                        user_id=user_id,
                        fn_name="getCandleData",
                        historicDataParams=params,
                    )
                return quantity, payload
            except Exception as exc:
                logger.warning("Angel One getCandleData failed: %s", exc)
                return None

        history_payloads = await asyncio.gather(
            *(fetch_holding_history(holding) for holding in holdings)
        )

        for result in history_payloads:
            if result is None:
                continue
            quantity, payload = result
            if not isinstance(payload, dict) or not payload.get("data"):
                continue

            candles = payload.get("data", [])
            for candle in candles:
                if not isinstance(candle, list) or len(candle) < 5:
                    continue
                timestamp_str = candle[0]
                close = float(candle[4])
                weighted_history[timestamp_str] = weighted_history.get(
                    timestamp_str, 0.0
                ) + (close * quantity)

        if current_total > 0:
            weighted_history[end_time.isoformat()] = current_total

        return [
            {
                "date": ts,
                "value": round(value, 2),
                "invested": round(total_invested, 2),
            }
            for ts, value in sorted(weighted_history.items())
        ]

    async def _fetch_portfolio_snapshot(
        self,
        *,
        user_id: str,
        trigger: str,
    ) -> dict[str, Any]:
        # Keep broker calls sequential so one forced token refresh cannot race
        # across concurrent requests on the same session.
        # Add delays between calls to avoid hitting Angel One API rate limits
        holdings_payload = await self._call_angel_one(
            user_id=user_id,
            fn_name="holding",
        )
        await asyncio.sleep(0.3)  # 300ms delay to avoid rate limiting

        positions_payload = await self._call_angel_one(
            user_id=user_id,
            fn_name="position",
        )
        await asyncio.sleep(0.3)  # 300ms delay

        order_payload = await self._call_angel_one(
            user_id=user_id,
            fn_name="orderBook",
        )
        await asyncio.sleep(0.3)  # 300ms delay

        try:
            funds_payload = await self._call_angel_one(
                user_id=user_id,
                fn_name="rmsLimit",
            )
        except Exception as exc:
            logger.warning("Angel One rmsLimit failed for user %s: %s", user_id, exc)
            funds_payload = {"data": {}}

        holdings = self._extract_angel_one_holdings(holdings_payload)

        holdings = [self._normalize_angel_one_holding(h) for h in holdings]
        positions = normalize_sequence_payload(positions_payload)
        order_history = normalize_sequence_payload(order_payload)
        funds = normalize_mapping_payload(funds_payload)

        summary = self._build_portfolio_totals(
            holdings=holdings,
            positions=positions,
            funds=funds,
        )

        performance_history = []
        current_val = summary.get("holdings_market_value") or 0
        if current_val > 0:
            performance_history.append(
                {
                    "date": datetime.now(UTC).date().isoformat(),
                    "value": current_val,
                }
            )

        now = datetime.now(UTC).isoformat()
        return {
            "user_id": user_id,
            "broker": ANGEL_ONE_BROKER,
            "trigger": trigger,
            "synced_at": now,
            "cache_ttl_seconds": self.settings.portfolio_cache_ttl_seconds,
            "holdings": holdings,
            "positions": positions,
            "order_history": order_history,
            "funds": funds,
            "performance_history": performance_history,
            "summary": summary,
        }

    async def _call_angel_one(self, *, user_id: str, fn_name: str, **kwargs) -> Any:
        ensure_angel_one_configured(self.settings)
        try:
            jwt_token = await self.broker_session_service.get_jwt(
                user_id=user_id,
                broker=ANGEL_ONE_BROKER,
            )
        except Exception as exc:
            logger.error(
                "Angel One get_jwt failed for user %s: %s",
                user_id,
                exc,
                exc_info=True,
            )
            raise

        try:
            payload = await asyncio.wait_for(
                self._execute_angel_one_call(
                    fn_name=fn_name,
                    jwt_token=jwt_token,
                    **kwargs,
                ),
                timeout=35.0,  # 35s total (SDK 30s + overhead)
            )
        except TimeoutError:
            logger.warning(
                "Angel One %s call timeout for user %s after 20 seconds",
                fn_name,
                user_id,
            )
            raise BrokerAuthError(
                f"Angel One {fn_name} request timed out. Please try again."
            ) from None
        except Exception as exc:
            logger.error(
                "Angel One %s API call failed for user %s: %s",
                fn_name,
                user_id,
                exc,
                exc_info=True,
            )
            raise

        if is_invalid_token_payload(payload):
            logger.warning(
                "Angel One %s rejected a JWT for user %s. Refreshing token.",
                fn_name,
                user_id,
            )
            try:
                jwt_token = await self.broker_session_service.refresh_token_if_needed(
                    user_id=user_id,
                    broker=ANGEL_ONE_BROKER,
                    force=True,
                )
            except Exception as exc:
                logger.error(
                    "Angel One token refresh failed for user %s: %s",
                    user_id,
                    exc,
                    exc_info=True,
                )
                raise

            try:
                payload = await asyncio.wait_for(
                    self._execute_angel_one_call(
                        fn_name=fn_name,
                        jwt_token=jwt_token,
                        **kwargs,
                    ),
                    timeout=35.0,  # Same timeout as initial call
                )
            except TimeoutError:
                logger.warning(
                    "Angel One %s call timeout (after token refresh) for %s",
                    fn_name,
                    user_id,
                )
                raise BrokerAuthError(
                    f"Angel One {fn_name} request timed out after token refresh."
                ) from None
            except Exception as exc:
                logger.error(
                    "Angel One %s API call failed (after refresh) for %s: %s",
                    fn_name,
                    user_id,
                    exc,
                    exc_info=True,
                )
                raise

        if is_invalid_token_payload(payload):
            raise BrokerAuthError(
                "Angel One session failed: token remains invalid after refresh."
            )

        raise_if_broker_payload_failed(payload, fn_name=fn_name)
        return payload

    async def _execute_angel_one_call(
        self,
        *,
        fn_name: str,
        jwt_token: str,
        **kwargs,
    ) -> Any:
        client = self._create_angel_one_client()
        bind_jwt_to_client(client=client, jwt_token=jwt_token)
        return await execute_read_call(client=client, fn_name=fn_name, **kwargs)

    def _create_angel_one_client(self):
        return create_smart_connect(self.settings)

    @staticmethod
    def _cache_version(broker_session: BrokerSession) -> dict[str, str]:
        return {
            "broker": broker_session.broker,
            "broker_session_id": str(broker_session.id),
            "broker_connected_at": broker_session.connected_at.isoformat(),
        }

    @staticmethod
    def _cache_record(
        *,
        snapshot: dict[str, Any],
        cache_version: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "schema": PORTFOLIO_CACHE_SCHEMA,
            **cache_version,
            "snapshot": snapshot,
        }

    @staticmethod
    def _extract_cached_snapshot(
        *,
        cached: Any,
        cache_version: dict[str, str],
    ) -> dict[str, Any] | None:
        if not isinstance(cached, dict):
            return None
        if cached.get("schema") != PORTFOLIO_CACHE_SCHEMA:
            return None
        for key, expected_value in cache_version.items():
            if cached.get(key) != expected_value:
                return None
        snapshot = cached.get("snapshot")
        return snapshot if isinstance(snapshot, dict) else None

    @classmethod
    def _build_portfolio_totals(
        cls,
        *,
        holdings: list[dict[str, Any]],
        positions: list[dict[str, Any]],
        funds: dict[str, Any],
    ) -> dict[str, float | None]:
        funds_total = cls._pick_numeric_value(
            funds,
            (
                "availablecash",
                "availableCash",
                "available_cash",
                "cash",
                "cashbalance",
                "cashBalance",
                "net",
                "netbalance",
                "netBalance",
                "clear_cash",
                "clearCash",
                "cnc_balance_available",
                "cncBalanceAvailable",
                # Groww margin API field names
                "availableMargin",
                "available_margin",
                "availablemargin",
                "clearingBalance",
                "clearing_balance",
                "clearingbalance",
                "balanceForTrading",
                "balance_for_trading",
                "balancefortrading",
                "adhocMargin",
                "adhoc_margin",
                "adhocmargin",
                "totalMargin",
                "total_margin",
                "totalmargin",
            ),
        )

        holdings_investment = 0.0
        holdings_market_value = 0.0
        positions_market_value = 0.0
        overall_gain = 0.0

        has_investment = False
        has_holdings_value = False
        has_positions_value = False
        has_gain = False

        for holding in holdings:
            quantity = cls._resolve_quantity(holding)
            average_price = cls._pick_numeric_value(
                holding,
                (
                    "averageprice",
                    "averagePrice",
                    "avgprice",
                    "avgPrice",
                    "average_price",
                    "costprice",
                    "costPrice",
                ),
            )
            invested_amount = cls._pick_numeric_value(
                holding,
                (
                    "invested",
                    "investedamount",
                    "investedAmount",
                    "invested_amount",
                    "buyamount",
                    "buyAmount",
                    "totalinvestment",
                    "totalInvestment",
                ),
            )
            if (
                invested_amount is None
                and quantity is not None
                and average_price is not None
            ):
                invested_amount = quantity * average_price
            if invested_amount is not None:
                holdings_investment += invested_amount
                has_investment = True

            current_value = cls._pick_numeric_value(
                holding,
                (
                    "currentvalue",
                    "currentValue",
                    "current_value",
                    "marketvalue",
                    "marketValue",
                    "market_value",
                    "ltpvalue",
                    "ltpValue",
                ),
            )
            ltp = cls._pick_numeric_value(
                holding,
                ("ltp", "lastprice", "lastPrice", "last_price", "close"),
            )
            if current_value is None and quantity is not None and ltp is not None:
                current_value = quantity * ltp
            if current_value is not None:
                holdings_market_value += current_value
                has_holdings_value = True

            pnl_value = cls._pick_numeric_value(
                holding,
                (
                    "pnl",
                    "profitandloss",
                    "profitAndLoss",
                    "unrealisedpnl",
                    "unrealisedPnL",
                    "unrealizedpnl",
                    "unrealizedPnL",
                    "gainloss",
                    "gainLoss",
                    "m2m",
                ),
            )
            if (
                pnl_value is None
                and current_value is not None
                and invested_amount is not None
            ):
                pnl_value = current_value - invested_amount
            if pnl_value is not None:
                overall_gain += pnl_value
                has_gain = True

        for position in positions:
            quantity = cls._resolve_quantity(position)
            ltp = cls._pick_numeric_value(
                position,
                ("ltp", "lastprice", "lastPrice", "closeprice", "closePrice"),
            )
            average_price = cls._pick_numeric_value(
                position,
                ("avgnetprice", "avgNetPrice", "averageprice", "averagePrice"),
            )
            if quantity is not None:
                absolute_quantity = abs(quantity)
                if ltp is not None:
                    positions_market_value += absolute_quantity * ltp
                    has_positions_value = True
                if average_price is not None:
                    holdings_investment += absolute_quantity * average_price
                    has_investment = True

            pnl_value = cls._pick_numeric_value(
                position,
                (
                    "pnl",
                    "m2m",
                    "unrealised",
                    "unrealisedPnl",
                    "unrealizedPnl",
                    "realised",
                ),
            )
            if pnl_value is not None:
                overall_gain += pnl_value
                has_gain = True

        return {
            "funds": funds_total,
            "investment": holdings_investment if has_investment else None,
            "holdings_market_value": (
                holdings_market_value if has_holdings_value else None
            ),
            "positions_market_value": (
                positions_market_value if has_positions_value else None
            ),
            "overall_gain": overall_gain if has_gain else None,
        }

    @staticmethod
    def _extract_angel_one_holdings(payload: Any) -> list[dict[str, Any]]:
        """Extract individual holding rows from Angel One's nested holding response.

        Angel One returns:
            {"data": {"holdings": [...], "totalholding": {...}}}

        ``normalize_sequence_payload`` would wrap the inner dict as a single-element
        list, which is wrong.  This helper drills into ``data.holdings`` first,
        then falls back to the generic normaliser for any other shape.
        """
        if not isinstance(payload, dict):
            return []

        data = payload.get("data")

        # Primary path: Angel One holding endpoint: data is a dict with a
        # "holdings" key whose value is the list of individual stock rows.
        if isinstance(data, dict):
            inner = data.get("holdings")
            if isinstance(inner, list):
                return [item for item in inner if isinstance(item, dict)]
            # data itself might already be a single holding dict
            return [data]

        # Fallback: data is already a flat list (other brokers / future formats)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]

        return []

    @classmethod
    def _normalize_angel_one_holding(cls, holding: dict[str, Any]) -> dict[str, Any]:
        """Normalize an Angel One holding to ensure all expected fields are present.

        Ensures consistent field names across all brokers for frontend compatibility.
        """
        normalized = dict(holding)

        # Extract symbol
        symbol = cls._pick_string_value(
            normalized,
            (
                "tradingsymbol",
                "tradingSymbol",
                "trading_symbol",
                "symbol",
                "name",
                "scrip",
            ),
        )
        if symbol:
            normalized["symbol"] = symbol

        # Extract quantity
        quantity = cls._resolve_quantity(normalized) or 0.0
        normalized["quantity"] = quantity

        # Extract average/buy price
        average_price = (
            cls._pick_numeric_value(
                normalized,
                (
                    "averagePrice",
                    "average_price",
                    "averageprice",
                    "avgPrice",
                    "avg_price",
                    "avgprice",
                    "buyPrice",
                    "buy_price",
                    "buyprice",
                    "costPrice",
                    "cost_price",
                    "costprice",
                ),
            )
            or 0.0
        )
        normalized["averagePrice"] = average_price
        if "average_price" not in normalized:
            normalized["average_price"] = average_price

        # Extract LTP (last traded price)
        ltp = cls._pick_numeric_value(
            normalized,
            (
                "ltp",
                "lastPrice",
                "last_price",
                "lastprice",
                "close",
                "closePrice",
                "close_price",
                "closeprice",
            ),
        )
        if ltp is not None:
            normalized["ltp"] = ltp

        # Extract invested amount
        invested_amount = cls._pick_numeric_value(
            normalized,
            (
                "investedAmount",
                "invested_amount",
                "investedamount",
                "totalInvestment",
                "total_investment",
                "totalinvestment",
                "buyAmount",
                "buy_amount",
                "buyamount",
                "costValue",
                "cost_value",
                "costvalue",
            ),
        )
        if invested_amount is None and quantity > 0 and average_price > 0:
            invested_amount = quantity * average_price
        if invested_amount is not None:
            normalized["investedAmount"] = invested_amount
            if "invested_amount" not in normalized:
                normalized["invested_amount"] = invested_amount

        # Extract current value
        current_value = cls._pick_numeric_value(
            normalized,
            (
                "currentValue",
                "current_value",
                "marketValue",
                "market_value",
                "ltpValue",
                "ltp_value",
            ),
        )
        if current_value is None and quantity > 0 and ltp is not None and ltp > 0:
            current_value = quantity * ltp
        if current_value is not None:
            normalized["currentValue"] = current_value
            if "current_value" not in normalized:
                normalized["current_value"] = current_value

        # Extract or compute PnL
        pnl = cls._pick_numeric_value(
            normalized,
            (
                "pnl",
                "profitAndLoss",
                "profit_and_loss",
                "profitandloss",
                "unrealisedPnl",
                "unrealised_pnl",
                "unrealizedPnl",
                "unrealized_pnl",
                "gainLoss",
                "gain_loss",
                "m2m",
            ),
        )
        if current_value is None and invested_amount is not None and pnl is not None:
            current_value = invested_amount + pnl
            normalized["currentValue"] = current_value
            if "current_value" not in normalized:
                normalized["current_value"] = current_value
        if pnl is None and invested_amount is not None and current_value is not None:
            pnl = current_value - invested_amount
        if pnl is not None:
            normalized["pnl"] = pnl

            # If we have pnl and current_value but missing invested_amount, compute it
            if (
                invested_amount is None or invested_amount <= 0
            ) and current_value is not None:
                invested_amount = current_value - pnl
                normalized["investedAmount"] = invested_amount
                if "invested_amount" not in normalized:
                    normalized["invested_amount"] = invested_amount

            # If we still don't have average_price but have invested_amount, compute it
            if (
                average_price <= 0
                and invested_amount is not None
                and invested_amount > 0
                and quantity > 0
            ):
                average_price = invested_amount / quantity
                normalized["averagePrice"] = average_price
                if "average_price" not in normalized:
                    normalized["average_price"] = average_price

        # Extract or compute PnL percentage
        pnl_percentage = cls._pick_numeric_value(
            normalized,
            (
                "pnlPercentage",
                "pnl_percentage",
                "pnlpercentage",
                "profitLossPercentage",
                "profit_loss_percentage",
                "gainLossPercentage",
                "gain_loss_percentage",
            ),
        )
        if (
            pnl_percentage is None
            and invested_amount is not None
            and invested_amount > 0
            and pnl is not None
        ):
            pnl_percentage = (pnl / invested_amount) * 100
        if pnl_percentage is not None:
            normalized["pnlPercentage"] = pnl_percentage
            if "pnl_percentage" not in normalized:
                normalized["pnl_percentage"] = pnl_percentage

        return normalized

    @staticmethod
    def _pick_string_value(
        source: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str | None:
        """Pick the first string value found from the given keys."""
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _resolve_quantity(cls, item: dict[str, Any]) -> float | None:
        direct_quantity = cls._pick_numeric_value(
            item,
            (
                "quantity",
                "qty",
                "holdingquantity",
                "holdingQuantity",
                "totalquantity",
                "totalQuantity",
                "netqty",
                "netQty",
                "buyqty",
                "buyQty",
                "sellqty",
                "sellQty",
            ),
        )
        if direct_quantity is not None:
            return direct_quantity

        settled_quantity = cls._pick_numeric_value(
            item,
            (
                "realisedquantity",
                "realisedQuantity",
                "realizedquantity",
                "realizedQuantity",
            ),
        )
        t1_quantity = cls._pick_numeric_value(item, ("t1quantity", "t1Quantity"))
        if settled_quantity is not None or t1_quantity is not None:
            return (settled_quantity or 0.0) + (t1_quantity or 0.0)
        return None

    @staticmethod
    def _pick_numeric_value(
        source: dict[str, Any],
        keys: tuple[str, ...],
    ) -> float | None:
        for key in keys:
            value = PortfolioSyncService._parse_numeric_value(source.get(key))
            if value is not None:
                return value
        return None

    @staticmethod
    def _parse_numeric_value(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            normalized = (
                value.replace(",", "").replace("\u20b9", "").replace("%", "").strip()
            )
            if not normalized:
                return None
            try:
                return float(normalized)
            except ValueError:
                return None
        return None
