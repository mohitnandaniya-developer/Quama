"""Separate worker process for Angel One live market data."""

from __future__ import annotations

import asyncio
import logging
import signal
import threading
from collections.abc import Iterable
from typing import Any

from sqlalchemy import select

from app.config import Settings, get_settings
from app.core.cache_keys import (
    market_channel,
    market_command_channel,
    market_snapshot_key,
)
from app.db.session import dispose_engine, get_session_maker, init_engine
from app.integrations.angel_one.market_data import (
    group_instruments_by_exchange,
    normalize_tick,
)
from app.integrations.angel_one.sdk import create_market_feed_client
from app.models.broker_session import BrokerSession
from app.services.broker_session_service import ANGEL_ONE_BROKER, BrokerSessionService
from app.services.cache_service import CacheService
from app.services.market_data_bus import MarketDataBus

logger = logging.getLogger(__name__)


class AngelOneMarketStreamWorker:
    """Run Angel One websocket feeds outside the FastAPI request lifecycle."""

    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings
        self.market_data_bus = MarketDataBus(redis_url=settings.market_data_bus_url)
        self.cache_service = CacheService(
            base_url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )
        self._connections: dict[str, MarketConnection] = {}
        self._reconcile_lock = asyncio.Lock()

    async def run(self, *, stop_event: asyncio.Event | None = None) -> None:
        """Start the control loop and keep the worker alive."""
        if not self.market_data_bus.enabled:
            msg = (
                "MARKET_DATA_REDIS_URL or REDIS_URL is required for the market worker."
            )
            raise RuntimeError(msg)

        resolved_stop_event = stop_event or asyncio.Event()
        await self.reconcile()
        tasks = {
            asyncio.create_task(self._poll_for_reconcile(resolved_stop_event)),
            asyncio.create_task(self._listen_for_commands(resolved_stop_event)),
            asyncio.create_task(resolved_stop_event.wait()),
        }
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()

    async def reconcile(self) -> None:
        """Align live websocket connections with Redis subscription intent."""
        async with self._reconcile_lock:
            desired = await self.market_data_bus.list_subscription_payloads()
            desired_user_ids = set(desired)
            active_sessions = await self._fetch_active_sessions(
                user_ids=desired_user_ids
            )

            for user_id, payload in desired.items():
                broker_session = active_sessions.get(user_id)
                if broker_session is None or not broker_session.feed_token:
                    await self._stop_connection(user_id=user_id)
                    continue

                auth_token = await self._get_user_auth_token(user_id=user_id)
                if not auth_token:
                    await self._stop_connection(user_id=user_id)
                    continue

                connection = self._connections.get(user_id)
                if (
                    connection is None
                    or not connection.matches_credentials(
                        client_code=broker_session.client_code,
                        auth_token=auth_token,
                        feed_token=broker_session.feed_token,
                    )
                    or not connection.is_running
                ):
                    await self._stop_connection(user_id=user_id)
                    connection = MarketConnection(
                        settings=self.settings,
                        user_id=user_id,
                        client_code=broker_session.client_code,
                        auth_token=auth_token,
                        feed_token=broker_session.feed_token,
                        market_data_bus=self.market_data_bus,
                    )
                    connection.start()
                    self._connections[user_id] = connection

                connection.update_subscriptions(
                    mode=int(payload.get("mode", 1)),
                    instruments=_normalize_instrument_payload(
                        payload.get("instruments", [])
                    ),
                )

            for user_id in list(self._connections):
                if user_id not in desired_user_ids:
                    await self._stop_connection(user_id=user_id)

    async def close(self) -> None:
        """Stop all live connections and release owned clients."""
        for user_id in list(self._connections):
            await self._stop_connection(user_id=user_id)
        await self.market_data_bus.close()
        await self.cache_service.close()

    async def _poll_for_reconcile(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.settings.market_worker_poll_interval_seconds,
                )
                return
            except TimeoutError:
                pass
            try:
                await self.reconcile()
            except Exception:
                logger.exception("Market worker reconcile polling failed.")

    async def _listen_for_commands(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                command_messages = self.market_data_bus.iter_channel_messages(
                    channels=[market_command_channel()],
                )
                async for _channel, _payload in command_messages:
                    if stop_event.is_set():
                        return
                    try:
                        await self.reconcile()
                    except Exception:
                        logger.exception("Market worker reconcile on command failed.")
            except Exception:
                logger.exception("Market worker command listener failed. Retrying.")
                await asyncio.sleep(1)

    async def _fetch_active_sessions(
        self,
        *,
        user_ids: set[str],
    ) -> dict[str, BrokerSession]:
        if not user_ids:
            return {}

        session_maker = get_session_maker()
        async with session_maker() as session:
            result = await session.execute(
                select(BrokerSession).where(
                    BrokerSession.broker == ANGEL_ONE_BROKER,
                    BrokerSession.is_active.is_(True),
                    BrokerSession.user_id.in_(sorted(user_ids)),
                )
            )
            return {row.user_id: row for row in result.scalars().all()}

    async def _get_user_auth_token(self, *, user_id: str) -> str | None:
        session_maker = get_session_maker()
        async with session_maker() as session:
            service = BrokerSessionService(
                session=session,
                cache_service=self.cache_service,
                settings=self.settings,
            )
            active = await service.get_active_session(
                user_id=user_id,
                broker=ANGEL_ONE_BROKER,
            )
            if active is None:
                return None
            try:
                return await service.get_jwt(user_id=user_id, broker=ANGEL_ONE_BROKER)
            except Exception:
                logger.exception(
                    "Unable to resolve Angel One JWT for user %s.",
                    user_id,
                )
                return None

    async def _stop_connection(self, *, user_id: str) -> None:
        connection = self._connections.pop(user_id, None)
        if connection is not None:
            connection.stop()


class MarketConnection:
    """One Angel One websocket connection for one user subscription set."""

    def __init__(
        self,
        *,
        settings: Settings,
        user_id: str,
        client_code: str,
        auth_token: str,
        feed_token: str,
        market_data_bus: MarketDataBus,
    ) -> None:
        self.settings = settings
        self.user_id = user_id
        self.client_code = client_code
        self.auth_token = auth_token
        self.feed_token = feed_token
        self.market_data_bus = market_data_bus
        self._loop = asyncio.get_running_loop()
        self._lock = threading.Lock()
        self._mode = 1
        self._instruments: list[dict[str, int | str]] = []
        self._client = create_market_feed_client(
            settings=settings,
            auth_token=auth_token,
            client_code=client_code,
            feed_token=feed_token,
        )
        self._client.on_open = self._on_open
        self._client.on_data = self._on_data
        self._client.on_close = self._on_close
        self._client.on_error = self._on_error
        self._connected = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        """Return whether the websocket thread is still active."""
        return self._connected.is_set() or bool(
            self._thread is not None and self._thread.is_alive()
        )

    def matches_credentials(
        self,
        *,
        client_code: str,
        auth_token: str,
        feed_token: str,
    ) -> bool:
        """Return whether the connection already owns these credentials."""
        return (
            self.client_code == client_code
            and self.auth_token == auth_token
            and self.feed_token == feed_token
        )

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._client.connect,
            name=f"angel-one-market-{self.user_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._connected.clear()
        try:
            self._client.close_connection()
        except Exception:
            logger.exception(
                "Failed to close market websocket for user %s.",
                self.user_id,
            )

    def update_subscriptions(
        self,
        *,
        mode: int,
        instruments: list[dict[str, int | str]],
    ) -> None:
        desired = _sort_instruments(instruments)
        with self._lock:
            previous = _sort_instruments(self._instruments)
            previous_set = _instrument_set(previous)
            desired_set = _instrument_set(desired)
            to_unsubscribe = previous_set - desired_set
            to_subscribe = desired_set - previous_set
            self._mode = mode
            self._instruments = desired

        if not self._connected.is_set():
            return

        if to_unsubscribe:
            self._client.unsubscribe(
                correlation_id=f"{self.user_id}-unsub",
                mode=mode,
                token_list=group_instruments_by_exchange(
                    _materialize_instrument_set(to_unsubscribe)
                ),
            )
        if to_subscribe:
            self._client.subscribe(
                correlation_id=f"{self.user_id}-sub",
                mode=mode,
                token_list=group_instruments_by_exchange(
                    _materialize_instrument_set(to_subscribe)
                ),
            )

    def _on_open(self, wsapp) -> None:
        del wsapp
        self._connected.set()
        with self._lock:
            if not self._instruments:
                return
            token_list = group_instruments_by_exchange(self._instruments)
            mode = self._mode
        self._client.subscribe(
            correlation_id=f"{self.user_id}-open",
            mode=mode,
            token_list=token_list,
        )

    def _on_data(self, wsapp, payload: dict[str, Any]) -> None:
        del wsapp
        normalized = normalize_tick(
            payload,
            price_scale=self.settings.angel_one_price_scale,
        )
        instrument_token = str(normalized.get("instrument_token", "")).strip()
        if not instrument_token:
            return
        asyncio.run_coroutine_threadsafe(
            self._publish_tick(instrument_token=instrument_token, tick=normalized),
            self._loop,
        )

    def _on_close(self, wsapp) -> None:
        del wsapp
        self._connected.clear()

    def _on_error(self, *args) -> None:
        logger.warning(
            "Angel One market websocket error for user %s: %s",
            self.user_id,
            args,
        )

    async def _publish_tick(
        self,
        *,
        instrument_token: str,
        tick: dict[str, Any],
    ) -> None:
        await self.market_data_bus.set_json(
            key=market_snapshot_key(instrument_token=instrument_token),
            payload=tick,
            ttl_seconds=self.settings.market_snapshot_ttl_seconds,
        )
        await self.market_data_bus.publish_json(
            channel=market_channel(instrument_token=instrument_token),
            payload=tick,
        )


def _sort_instruments(
    instruments: Iterable[dict[str, int | str]],
) -> list[dict[str, int | str]]:
    return sorted(
        [
            {
                "exchange_type": int(item["exchange_type"]),
                "instrument_token": str(item["instrument_token"]),
            }
            for item in instruments
        ],
        key=lambda item: (int(item["exchange_type"]), str(item["instrument_token"])),
    )


def _instrument_set(
    instruments: Iterable[dict[str, int | str]],
) -> set[tuple[int, str]]:
    return {
        (int(item["exchange_type"]), str(item["instrument_token"]))
        for item in instruments
    }


def _materialize_instrument_set(
    items: set[tuple[int, str]],
) -> list[dict[str, int | str]]:
    return [
        {"exchange_type": exchange_type, "instrument_token": token}
        for exchange_type, token in sorted(items)
    ]


def _normalize_instrument_payload(raw: Any) -> list[dict[str, int | str]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, int | str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        exchange_type = item.get("exchange_type")
        instrument_token = item.get("instrument_token")
        if exchange_type is None or instrument_token is None:
            continue
        items.append(
            {
                "exchange_type": int(exchange_type),
                "instrument_token": str(instrument_token),
            }
        )
    return items


async def main() -> None:
    """Run the standalone Angel One market worker."""
    settings = get_settings()
    init_engine(settings.database_url, echo=settings.debug)
    worker = AngelOneMarketStreamWorker(settings=settings)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown(signum, _frame) -> None:
        logger.info("Received signal %s. Stopping market worker.", signum)
        loop.call_soon_threadsafe(stop_event.set)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, request_shutdown)

    try:
        await worker.run(stop_event=stop_event)
    finally:
        await worker.close()
        await dispose_engine()
