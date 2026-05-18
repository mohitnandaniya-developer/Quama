"""Broker integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.cache_keys import (
    broker_jwt_key,
    market_command_channel,
    market_subscription_key,
    portfolio_snapshot_key,
)
from app.core.encryption import decrypt, encrypt
from app.core.llm_factory import LLMFactory
from app.db.session import get_session_maker
from app.models.broker_session import BrokerSession
from app.services.broker_session_service import (
    ANGEL_ONE_BROKER,
    GROWW_BROKER,
    BrokerSessionService,
    refresh_all_expiring_tokens,
)
from app.services.brokers.groww_service import GrowwBrokerService
from app.services.portfolio_sync_service import PortfolioSyncService


class FakeSmartApiFactory:
    """Build fake SmartAPI clients with shared scripted responses."""

    def __init__(self) -> None:
        self.session_payloads: list[dict[str, object]] = []
        self.profile_calls: list[str] = []
        self.terminate_calls: list[str] = []
        self.holdings_payload: dict[str, object] = {
            "data": [{"tradingsymbol": "INFY-EQ", "quantity": 3}]
        }
        self.positions_payload: dict[str, object] = {
            "data": [{"tradingsymbol": "NIFTY24APR", "netqty": 1}]
        }
        self.order_book_payload: dict[str, object] = {"data": []}
        self.funds_payload: dict[str, object] = {"data": {"availablecash": 125000.5}}
        self.refresh_payloads: dict[str, dict[str, object]] = {
            "refresh-1": {
                "data": {
                    "jwtToken": "jwt-refreshed-1",
                    "feedToken": "feed-refreshed-1",
                }
            },
            "refresh-good": {
                "data": {
                    "jwtToken": "jwt-refreshed-good",
                    "feedToken": "feed-refreshed-good",
                }
            },
        }

    def build(self):
        factory = self

        class FakeSmartConnect:
            def __init__(self) -> None:
                self.jwtToken: str | None = None

            def generateSession(
                self,
                client_code: str,
                password: str,
                totp: str,
            ) -> dict[str, object]:
                del password
                if totp == "000000":
                    raise RuntimeError("Invalid totp")
                if not factory.session_payloads:
                    raise RuntimeError("No scripted session payload available")
                return factory.session_payloads.pop(0)

            def getProfile(self, refresh_token: str) -> dict[str, object]:
                factory.profile_calls.append(refresh_token)
                return {"data": {"name": "Broker User"}}

            def holding(self) -> dict[str, object]:
                return factory.holdings_payload

            def position(self) -> dict[str, object]:
                return factory.positions_payload

            def rmsLimit(self) -> dict[str, object]:
                return factory.funds_payload

            def orderBook(self) -> dict[str, object]:
                return factory.order_book_payload

            def terminateSession(self, client_code: str) -> dict[str, object]:
                factory.terminate_calls.append(client_code)
                return {"status": True}

            def generateToken(self, refresh_token: str) -> dict[str, object]:
                if refresh_token == "refresh-bad":
                    raise RuntimeError("refresh failed")
                payload = factory.refresh_payloads.get(refresh_token)
                if payload is None:
                    raise RuntimeError("missing refresh payload")
                return payload

        return FakeSmartConnect()


def test_market_data_bus_url_falls_back_to_direct_upstash_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The market-data pipeline can reuse a direct Upstash Redis URL."""
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-test-key")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    monkeypatch.setenv(
        "UPSTASH_REDIS_REST_URL",
        "rediss://default:token@example.upstash.io:6379",
    )
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("MARKET_DATA_REDIS_URL", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test-market-url.db")
    monkeypatch.setenv("ANGEL_ONE_MARKET_API_KEY", "angel-api-key")
    monkeypatch.setenv("ANGEL_ONE_SECRET_KEY", "angel-secret")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.market_data_bus_url == settings.upstash_redis_rest_url

    get_settings.cache_clear()


async def _fetch_broker_session(
    user_id: str,
    broker: str = ANGEL_ONE_BROKER,
) -> BrokerSession:
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(BrokerSession).where(
                BrokerSession.user_id == user_id,
                BrokerSession.broker == broker,
            )
        )
        row = result.scalar_one()
        await session.refresh(row)
        return row


@pytest.fixture
def smart_api_factory(monkeypatch: pytest.MonkeyPatch) -> FakeSmartApiFactory:
    """Patch broker service client construction with a fake SmartAPI client."""
    factory = FakeSmartApiFactory()
    monkeypatch.setattr(
        BrokerSessionService,
        "_create_angel_one_client",
        lambda self: factory.build(),
    )
    monkeypatch.setattr(
        PortfolioSyncService,
        "_create_angel_one_client",
        lambda self: factory.build(),
    )
    return factory


def test_encrypt_decrypt_round_trip(test_settings) -> None:
    """Broker token encryption round-trips through Fernet."""
    del test_settings
    cipher_text = encrypt("jwt-secret")

    assert cipher_text != "jwt-secret"
    assert decrypt(cipher_text) == "jwt-secret"


@pytest.mark.asyncio
async def test_connect_angel_one_upserts_and_encrypts_tokens(
    client,
    fake_cache_service,
    smart_api_factory: FakeSmartApiFactory,
    test_settings,
    user_headers,
) -> None:
    """Connecting twice reuses one row, encrypts tokens, and refreshes the JWT cache."""
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-initial",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A1001",
            }
        },
        {
            "data": {
                "jwtToken": "jwt-updated",
                "refreshToken": "refresh-1",
                "feedToken": "feed-2",
                "clientcode": "A1001",
            }
        },
    ]

    first_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A1001",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    second_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A1001",
            "password": "broker-pass",
            "totp": "123456",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    row = await _fetch_broker_session("test-user")
    assert row.client_code == "A1001"
    assert row.is_active is True
    assert row.jwt_token != "jwt-updated"
    assert row.refresh_token != "refresh-1"
    assert decrypt(row.jwt_token) == "jwt-updated"
    assert decrypt(row.refresh_token) == "refresh-1"

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(select(BrokerSession))
        assert len(list(result.scalars().all())) == 1

    cache_key = broker_jwt_key(user_id="test-user", broker=ANGEL_ONE_BROKER)
    assert fake_cache_service.store[cache_key] == "jwt-updated"
    assert (
        fake_cache_service.ttl_by_key[cache_key]
        == test_settings.broker_jwt_cache_ttl_seconds
    )


@pytest.mark.asyncio
async def test_connect_groww_uses_api_key_totp_and_returns_portfolio(
    client,
    fake_cache_service,
    monkeypatch: pytest.MonkeyPatch,
    test_settings,
    user_headers,
) -> None:
    """Groww stores the SDK access token and returns SDK portfolio data."""

    async def fake_access_token(
        self: BrokerSessionService,
        *,
        api_key: str,
        totp: str,
    ) -> str:
        del self
        assert api_key == "groww-user-api-key"
        assert totp == "654321"
        return "groww-access-token"

    class FakeGrowwClient:
        def get_holdings_for_user(self, *, timeout: int) -> dict[str, object]:
            assert timeout == 5
            return {
                "holdings": [
                    {
                        "trading_symbol": "RELIANCE",
                        "quantity": 2,
                        "average_buy_price": 100.0,
                        "ltp": 125.0,
                    },
                    {
                        "trading_symbol": "IRFC",
                        "quantity": "3",
                        "invested_amount": "300",
                    },
                ]
            }

        def get_ltp(
            self,
            exchange_trading_symbols: tuple[str, ...],
            segment: str,
            *,
            timeout: int,
        ) -> dict[str, object]:
            assert exchange_trading_symbols == ("NSE_RELIANCE", "NSE_IRFC")
            assert segment == "CASH"
            assert timeout == 5
            return {
                "payload": {
                    "NSE_RELIANCE": 130.0,
                    "NSE_IRFC": {"ltp": 120.0},
                }
            }

        def get_historical_candles(
            self,
            exchange: str,
            segment: str,
            groww_symbol: str,
            start_time: str,
            end_time: str,
            candle_interval: str,
            *,
            timeout: int,
        ) -> dict[str, object]:
            del start_time, end_time
            assert exchange == "NSE"
            assert segment == "CASH"
            assert candle_interval == "1day"
            assert timeout == 5
            close_by_symbol = {
                "RELIANCE": (100.0, 130.0),
                "IRFC": (100.0, 120.0),
            }
            first_close, second_close = close_by_symbol[groww_symbol]
            return {
                "payload": {
                    "candles": [
                        ["2020-01-01T00:00:00+05:30", 0, 0, 0, first_close],
                        ["2020-01-02T00:00:00+05:30", 0, 0, 0, second_close],
                    ]
                }
            }

        def get_positions_for_user(self) -> dict[str, object]:
            return {"positions": []}

        def get_available_margin_details(self) -> dict[str, object]:
            return {"clear_cash": 5000.0}

    def fake_create_groww_client(
        self: GrowwBrokerService,
        access_token: str,
    ) -> FakeGrowwClient:
        del self
        assert access_token == "groww-access-token"
        return FakeGrowwClient()

    monkeypatch.setattr(
        BrokerSessionService,
        "_request_groww_access_token",
        fake_access_token,
    )
    monkeypatch.setattr(
        GrowwBrokerService,
        "_create_groww_client",
        fake_create_groww_client,
    )

    connect_response = await client.post(
        "/api/v1/brokers/groww/connect",
        headers=user_headers,
        json={
            "api_key": "groww-user-api-key",
            "totp": "654321",
        },
    )
    portfolio_response = await client.get(
        "/api/v1/brokers/groww/portfolio",
        headers=user_headers,
    )

    assert connect_response.status_code == 200
    assert connect_response.json()["client_code"] == "API ...-key"

    row = await _fetch_broker_session("test-user", broker=GROWW_BROKER)
    assert row.client_code == "API ...-key"
    assert decrypt(row.jwt_token) == "groww-access-token"
    assert decrypt(row.refresh_token) == ""

    cache_key = broker_jwt_key(user_id="test-user", broker=GROWW_BROKER)
    assert fake_cache_service.store[cache_key] == "groww-access-token"
    assert (
        fake_cache_service.ttl_by_key[cache_key]
        == test_settings.broker_jwt_cache_ttl_seconds
    )

    assert portfolio_response.status_code == 200
    portfolio = portfolio_response.json()
    assert portfolio["connected_broker"] == GROWW_BROKER
    assert portfolio["holdings"][0]["symbol"] == "RELIANCE"
    assert portfolio["holdings"][0]["average_price"] == 100.0
    assert portfolio["holdings"][0]["ltp"] == 130.0
    assert portfolio["holdings"][1]["average_price"] == 100.0
    assert portfolio["holdings"][1]["current_value"] == 360.0
    assert portfolio["summary"] == {
        "funds": 5000.0,
        "investment": 500.0,
        "overall_gain": 120.0,
    }
    assert {"date": "2020-01-01", "value": 500.0} in portfolio["performance_history"]
    assert {"date": "2020-01-02", "value": 620.0} in portfolio["performance_history"]


@pytest.mark.asyncio
async def test_groww_ltp_fetch_retries_individual_symbols_when_batch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One rejected Groww LTP symbol should not erase prices for all holdings."""

    class FakeBrokerSessionService:
        async def get_jwt(self, *, user_id: str, broker: str) -> str:
            assert user_id == "test-user"
            assert broker == GROWW_BROKER
            return "groww-access-token"

    class FakeGrowwClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        def get_ltp(
            self,
            exchange_trading_symbols: tuple[str, ...],
            segment: str,
            *,
            timeout: int,
        ) -> dict[str, object]:
            assert segment == "CASH"
            assert timeout == 5
            self.calls.append(exchange_trading_symbols)
            if len(exchange_trading_symbols) > 1:
                raise RuntimeError("invalid symbol in batch")
            if exchange_trading_symbols == ("NSE_IRFC",):
                return {"payload": {"NSE_IRFC": 120.0}}
            raise RuntimeError("symbol not found")

    groww_client = FakeGrowwClient()

    monkeypatch.setattr(
        GrowwBrokerService,
        "_create_groww_client",
        lambda self, access_token: groww_client,
    )

    service = GrowwBrokerService(
        broker_session_service=FakeBrokerSessionService(),
    )

    ltp_by_symbol = await service._fetch_ltp_map(
        user_id="test-user",
        holdings=[
            {"trading_symbol": "IRFC", "quantity": 10},
            {"trading_symbol": "BADTOKEN", "quantity": 1},
        ],
    )

    assert groww_client.calls == [
        ("NSE_IRFC", "NSE_BADTOKEN"),
        ("NSE_IRFC",),
        ("NSE_BADTOKEN",),
    ]
    assert ltp_by_symbol["IRFC"] == 120.0


@pytest.mark.asyncio
async def test_groww_ltp_fetch_uses_quote_fallback_when_ltp_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Groww quote fallback supplies last_price when LTP returns no symbol values."""

    class FakeBrokerSessionService:
        async def get_jwt(self, *, user_id: str, broker: str) -> str:
            assert user_id == "test-user"
            assert broker == GROWW_BROKER
            return "groww-access-token"

    class FakeGrowwClient:
        def get_ltp(
            self,
            exchange_trading_symbols: tuple[str, ...],
            segment: str,
            *,
            timeout: int,
        ) -> dict[str, object]:
            assert exchange_trading_symbols == ("NSE_IRFC",)
            assert segment == "CASH"
            assert timeout == 5
            return {"status": "SUCCESS", "payload": {}}

        def get_quote(
            self,
            trading_symbol: str,
            exchange: str,
            segment: str,
            *,
            timeout: int,
        ) -> dict[str, object]:
            assert trading_symbol == "IRFC"
            assert exchange == "NSE"
            assert segment == "CASH"
            assert timeout == 5
            return {
                "status": "SUCCESS",
                "payload": {
                    "average_price": 100.0,
                    "last_price": 112.5,
                },
            }

    monkeypatch.setattr(
        GrowwBrokerService,
        "_create_groww_client",
        lambda self, access_token: FakeGrowwClient(),
    )

    service = GrowwBrokerService(
        broker_session_service=FakeBrokerSessionService(),
    )

    ltp_by_symbol = await service._fetch_ltp_map(
        user_id="test-user",
        holdings=[{"trading_symbol": "IRFC", "quantity": 10}],
    )
    holding = service._normalize_holding(
        {"trading_symbol": "IRFC", "quantity": 10, "average_price": 98.14},
        ltp_by_symbol=ltp_by_symbol,
    )

    assert holding["ltp"] == 112.5
    assert holding["current_value"] == 1125.0
    assert holding["pnl"] == pytest.approx(143.6)


@pytest.mark.asyncio
async def test_disconnect_clears_cache_and_marks_session_inactive(
    client,
    fake_cache_service,
    smart_api_factory: FakeSmartApiFactory,
    user_headers,
) -> None:
    """Disconnect clears broker caches and deactivates the stored session."""
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-connect",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A2002",
            }
        }
    ]

    connect_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A2002",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    assert connect_response.status_code == 200

    await client.get("/api/v1/brokers/angel-one/holdings", headers=user_headers)
    await client.get("/api/v1/brokers/angel-one/positions", headers=user_headers)
    await client.get("/api/v1/brokers/angel-one/funds", headers=user_headers)

    disconnect_response = await client.delete(
        "/api/v1/brokers/angel-one/disconnect",
        headers=user_headers,
    )

    assert disconnect_response.status_code == 200
    assert disconnect_response.json() == {"disconnected": True}
    assert smart_api_factory.terminate_calls == ["A2002"]

    row = await _fetch_broker_session("test-user")
    assert row.is_active is False
    assert row.jwt_token == ""
    assert row.refresh_token == ""
    assert row.feed_token is None

    assert (
        broker_jwt_key(user_id="test-user", broker=ANGEL_ONE_BROKER)
        not in fake_cache_service.store
    )
    assert portfolio_snapshot_key(user_id="test-user") not in fake_cache_service.store


@pytest.mark.asyncio
async def test_broker_data_endpoints_cache_expected_ttls(
    client,
    fake_cache_service,
    smart_api_factory: FakeSmartApiFactory,
    test_settings,
    user_headers,
) -> None:
    """Portfolio sync owns the REST snapshot cache.

    Broker-facing endpoints stay compatible.
    """
    smart_api_factory.holdings_payload = {
        "data": [
            {
                "tradingsymbol": "INFY-EQ",
                "quantity": 3,
                "averageprice": 1500,
                "ltp": 1650,
            },
            {
                "tradingsymbol": "TCS-EQ",
                "quantity": "2",
                "investedamount": "6000",
                "pnl": "400",
            },
        ]
    }
    smart_api_factory.funds_payload = {
        "data": {
            "availablecash": 125000.5,
            "net": 125000.5,
        }
    }
    smart_api_factory.order_book_payload = {
        "data": [{"orderid": "ord-1", "tradingsymbol": "INFY-EQ", "status": "complete"}]
    }
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-connect",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A3003",
            }
        }
    ]

    connect_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A3003",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    assert connect_response.status_code == 200

    holdings_response = await client.get(
        "/api/v1/brokers/angel-one/holdings",
        headers=user_headers,
    )
    positions_response = await client.get(
        "/api/v1/brokers/angel-one/positions",
        headers=user_headers,
    )
    funds_response = await client.get(
        "/api/v1/brokers/angel-one/funds",
        headers=user_headers,
    )
    portfolio_response = await client.get(
        "/api/v1/brokers/angel-one/portfolio",
        headers=user_headers,
    )
    sync_response = await client.post(
        "/api/v1/portfolio/sync",
        headers=user_headers,
        json={"trigger": "user_action", "force_refresh": False},
    )
    status_response = await client.get(
        "/api/v1/brokers/status",
        headers=user_headers,
    )

    assert holdings_response.status_code == 200
    assert positions_response.status_code == 200
    assert funds_response.status_code == 200
    assert portfolio_response.status_code == 200
    assert sync_response.status_code == 200
    assert status_response.status_code == 200

    holdings_payload = holdings_response.json()
    assert [holding["tradingsymbol"] for holding in holdings_payload] == [
        "INFY-EQ",
        "TCS-EQ",
    ]
    assert holdings_payload[0]["quantity"] == 3.0
    assert holdings_payload[0]["averagePrice"] == 1500.0
    assert holdings_payload[0]["currentValue"] == 4950.0
    assert positions_response.json() == [{"tradingsymbol": "NIFTY24APR", "netqty": 1}]
    assert funds_response.json() == {"availablecash": 125000.5, "net": 125000.5}
    portfolio_payload = portfolio_response.json()
    assert [holding["tradingsymbol"] for holding in portfolio_payload["holdings"]] == [
        "INFY-EQ",
        "TCS-EQ",
    ]
    assert portfolio_payload["funds"] == {"availablecash": 125000.5, "net": 125000.5}
    assert portfolio_payload["summary"] == {
        "funds": 125000.5,
        "investment": 10500.0,
        "overall_gain": 850.0,
    }
    assert portfolio_payload["connected_broker"] == "angel_one"
    assert portfolio_payload["performance_history"] == []
    assert sync_response.json()["positions"] == [
        {"tradingsymbol": "NIFTY24APR", "netqty": 1}
    ]
    assert sync_response.json()["order_history"] == [
        {"orderid": "ord-1", "tradingsymbol": "INFY-EQ", "status": "complete"}
    ]
    assert sync_response.json()["summary"] == {
        "funds": 125000.5,
        "investment": 10500.0,
        "holdings_market_value": 4950.0,
        "positions_market_value": None,
        "overall_gain": 850.0,
    }
    assert status_response.json()["items"][0]["broker"] == "angel_one"

    assert (
        fake_cache_service.ttl_by_key[portfolio_snapshot_key(user_id="test-user")]
        == test_settings.portfolio_cache_ttl_seconds
    )


@pytest.mark.asyncio
async def test_portfolio_cache_is_ignored_when_broker_session_is_inactive(
    client,
    fake_cache_service,
    smart_api_factory: FakeSmartApiFactory,
    user_headers,
) -> None:
    """A stale portfolio cache cannot outlive the active broker session."""
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-connect",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A3500",
            }
        }
    ]

    connect_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A3500",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    assert connect_response.status_code == 200

    first_response = await client.get(
        "/api/v1/brokers/angel-one/holdings",
        headers=user_headers,
    )
    assert first_response.status_code == 200
    assert portfolio_snapshot_key(user_id="test-user") in fake_cache_service.store

    session_maker = get_session_maker()
    async with session_maker() as session:
        row = (
            await session.execute(
                select(BrokerSession).where(
                    BrokerSession.user_id == "test-user",
                    BrokerSession.broker == ANGEL_ONE_BROKER,
                )
            )
        ).scalar_one()
        row.is_active = False
        await session.commit()

    stale_response = await client.get(
        "/api/v1/brokers/angel-one/holdings",
        headers=user_headers,
    )

    assert stale_response.status_code == 404
    assert stale_response.json()["error"]["code"] == "broker_session_not_found"
    assert portfolio_snapshot_key(user_id="test-user") not in fake_cache_service.store


@pytest.mark.asyncio
async def test_connect_returns_structured_totp_error(
    client,
    smart_api_factory: FakeSmartApiFactory,
    user_headers,
) -> None:
    """Wrong TOTP returns the broker-specific AppError envelope."""
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-unused",
                "refreshToken": "refresh-unused",
                "feedToken": "feed-unused",
                "clientcode": "A4004",
            }
        }
    ]

    response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A4004",
            "password": "broker-pass",
            "totp": "000000",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "broker_totp_failed",
        "message": "Wrong TOTP.",
    }


@pytest.mark.asyncio
async def test_market_subscription_registration_persists_registry_and_publishes_command(
    client,
    fake_market_data_bus,
    smart_api_factory: FakeSmartApiFactory,
    test_settings,
    user_headers,
) -> None:
    """The market pipeline stores desired subscriptions outside the request path."""
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-market",
                "refreshToken": "refresh-1",
                "feedToken": "feed-market",
                "clientcode": "A4100",
            }
        }
    ]

    connect_response = await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A4100",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    assert connect_response.status_code == 200

    response = await client.post(
        "/api/v1/market/subscriptions",
        headers=user_headers,
        json={
            "mode": 1,
            "replace": True,
            "instruments": [
                {"exchange_type": 1, "instrument_token": "26009"},
                {"exchange_type": 1, "instrument_token": "3045"},
            ],
        },
    )
    duplicate_response = await client.post(
        "/api/v1/market/subscriptions",
        headers=user_headers,
        json={
            "mode": 1,
            "replace": True,
            "instruments": [
                {"exchange_type": 1, "instrument_token": "26009"},
                {"exchange_type": 1, "instrument_token": "3045"},
            ],
        },
    )

    assert response.status_code == 200
    assert duplicate_response.status_code == 200
    assert response.json() == {
        "user_id": "test-user",
        "broker": "angel_one",
        "mode": 1,
        "replace": True,
        "instruments": [
            {"exchange_type": 1, "instrument_token": "26009"},
            {"exchange_type": 1, "instrument_token": "3045"},
        ],
        "subscription_key": market_subscription_key(user_id="test-user"),
        "command_channel": market_command_channel(),
    }
    assert fake_market_data_bus.json_store[
        market_subscription_key(user_id="test-user")
    ] == {
        "user_id": "test-user",
        "broker": "angel_one",
        "mode": 1,
        "replace": True,
        "instruments": [
            {"exchange_type": 1, "instrument_token": "26009"},
            {"exchange_type": 1, "instrument_token": "3045"},
        ],
        "_ttl_seconds": test_settings.market_subscription_ttl_seconds,
    }
    assert fake_market_data_bus.published == [
        (
            market_command_channel(),
            {
                "type": "subscription_update",
                "user_id": "test-user",
                "broker": "angel_one",
                "mode": 1,
                "replace": True,
                "instruments": [
                    {"exchange_type": 1, "instrument_token": "26009"},
                    {"exchange_type": 1, "instrument_token": "3045"},
                ],
            },
        )
    ]


@pytest.mark.asyncio
async def test_chat_send_injects_portfolio_context_when_connected(
    client,
    smart_api_factory: FakeSmartApiFactory,
    user_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-streaming chat prepends the broker portfolio system message."""
    captured_messages = []

    class FakeLLM:
        async def ainvoke(self, messages):
            captured_messages.extend(messages)
            return SimpleNamespace(
                content="Portfolio-aware reply",
                usage_metadata={"total_tokens": 17},
            )

    monkeypatch.setattr(
        LLMFactory,
        "get_llm",
        staticmethod(lambda provider, model_name: FakeLLM()),
    )
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-connect",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A5005",
            }
        }
    ]

    await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A5005",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o", "title": "Broker chat"},
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/message",
        headers=user_headers,
        json={"conversation_id": conversation_id, "content": "Summarize my portfolio"},
    )

    assert response.status_code == 201
    portfolio_system_messages = [
        message.content
        for message in captured_messages
        if getattr(message, "type", "") == "system"
        and "Angel One Portfolio" in message.content
    ]
    assert portfolio_system_messages
    assert "INFY-EQ" in portfolio_system_messages[0]
    assert "125000.5" in portfolio_system_messages[0]


@pytest.mark.asyncio
async def test_chat_stream_injects_portfolio_context_when_connected(
    client,
    smart_api_factory: FakeSmartApiFactory,
    user_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming chat uses the same broker portfolio system message injection."""
    captured_messages = []

    class FakeLLM:
        async def astream(self, messages) -> AsyncIterator[SimpleNamespace]:
            captured_messages.extend(messages)
            yield SimpleNamespace(content="stream")
            yield SimpleNamespace(content="-reply")

    monkeypatch.setattr(
        LLMFactory,
        "get_llm",
        staticmethod(lambda provider, model_name: FakeLLM()),
    )
    smart_api_factory.session_payloads = [
        {
            "data": {
                "jwtToken": "jwt-connect",
                "refreshToken": "refresh-1",
                "feedToken": "feed-1",
                "clientcode": "A6006",
            }
        }
    ]

    await client.post(
        "/api/v1/brokers/angel-one/connect",
        headers=user_headers,
        json={
            "client_code": "A6006",
            "password": "broker-pass",
            "totp": "123456",
        },
    )
    conversation_response = await client.post(
        "/api/v1/conversations",
        headers=user_headers,
        json={"provider": "openai", "model_name": "gpt-4o"},
    )
    conversation_id = conversation_response.json()["id"]

    response = await client.post(
        "/api/v1/chat/stream",
        headers=user_headers,
        json={"conversation_id": conversation_id, "content": "What am I holding?"},
    )

    assert response.status_code == 200
    body = await response.aread()
    assert b"stream" in body
    assert b"[DONE]" in body

    portfolio_system_messages = [
        message.content
        for message in captured_messages
        if getattr(message, "type", "") == "system"
        and "Angel One Portfolio" in message.content
    ]
    assert portfolio_system_messages


@pytest.mark.asyncio
async def test_refresh_all_expiring_tokens_continues_after_errors(
    client,
    fake_cache_service,
    smart_api_factory: FakeSmartApiFactory,
    test_settings,
) -> None:
    """Background refresh updates stale rows and continues after failures."""
    del client
    now = datetime.now(UTC)
    session_maker = get_session_maker()

    async with session_maker() as session:
        stale_good = BrokerSession(
            user_id="stale-good",
            broker=ANGEL_ONE_BROKER,
            client_code="A7007",
            jwt_token=encrypt("jwt-old-good"),
            refresh_token=encrypt("refresh-good"),
            feed_token="feed-old-good",
            is_active=True,
            connected_at=now - timedelta(hours=30),
            token_refreshed_at=now - timedelta(hours=23),
            expires_at=now - timedelta(hours=1),
        )
        stale_bad = BrokerSession(
            user_id="stale-bad",
            broker=ANGEL_ONE_BROKER,
            client_code="A8008",
            jwt_token=encrypt("jwt-old-bad"),
            refresh_token=encrypt("refresh-bad"),
            feed_token="feed-old-bad",
            is_active=True,
            connected_at=now - timedelta(hours=30),
            token_refreshed_at=now - timedelta(hours=23),
            expires_at=now - timedelta(hours=1),
        )
        fresh_row = BrokerSession(
            user_id="fresh-user",
            broker=ANGEL_ONE_BROKER,
            client_code="A9009",
            jwt_token=encrypt("jwt-fresh"),
            refresh_token=encrypt("refresh-1"),
            feed_token="feed-fresh",
            is_active=True,
            connected_at=now - timedelta(hours=3),
            token_refreshed_at=now - timedelta(hours=1),
            expires_at=now + timedelta(hours=20),
        )
        session.add_all([stale_good, stale_bad, fresh_row])
        await session.commit()

    async with session_maker() as session:
        await refresh_all_expiring_tokens(
            session,
            fake_cache_service,
            test_settings,
        )

    async with session_maker() as session:
        result = await session.execute(
            select(BrokerSession).order_by(BrokerSession.user_id.asc())
        )
        rows = {row.user_id: row for row in result.scalars().all()}

    assert decrypt(rows["stale-good"].jwt_token) == "jwt-refreshed-good"
    assert rows["stale-good"].feed_token == "feed-refreshed-good"
    assert decrypt(rows["stale-bad"].jwt_token) == "jwt-old-bad"
    assert decrypt(rows["fresh-user"].jwt_token) == "jwt-fresh"
    assert (
        fake_cache_service.store[
            broker_jwt_key(user_id="stale-good", broker=ANGEL_ONE_BROKER)
        ]
        == "jwt-refreshed-good"
    )
    assert (
        fake_cache_service.ttl_by_key[
            broker_jwt_key(user_id="stale-good", broker=ANGEL_ONE_BROKER)
        ]
        == test_settings.broker_jwt_cache_ttl_seconds
    )


# ---------------------------------------------------------------------------
# Unit tests for GrowwBrokerService._to_colon_format
# ---------------------------------------------------------------------------


class TestToColonFormat:
    """Unit tests for the _to_colon_format static helper."""

    def test_nse_prefix_converted(self) -> None:
        """NSE_RELIANCE should become NSE:RELIANCE."""
        assert GrowwBrokerService._to_colon_format("NSE_RELIANCE") == "NSE:RELIANCE"

    def test_bse_prefix_converted(self) -> None:
        """BSE_TCS should become BSE:TCS."""
        assert GrowwBrokerService._to_colon_format("BSE_TCS") == "BSE:TCS"

    def test_no_recognized_prefix_passthrough(self) -> None:
        """A symbol with no NSE/BSE prefix is returned unchanged."""
        assert GrowwBrokerService._to_colon_format("RELIANCE") == "RELIANCE"

    def test_already_colon_format_is_idempotent(self) -> None:
        """A symbol already in colon format is returned unchanged."""
        assert GrowwBrokerService._to_colon_format("NSE:RELIANCE") == "NSE:RELIANCE"

    def test_bse_already_colon_format_is_idempotent(self) -> None:
        """BSE colon-format symbol is returned unchanged."""
        assert GrowwBrokerService._to_colon_format("BSE:TCS") == "BSE:TCS"

    def test_only_first_underscore_replaced(self) -> None:
        """Only the exchange-prefix underscore is replaced; others are kept."""
        assert (
            GrowwBrokerService._to_colon_format("NSE_SOME_SYMBOL") == "NSE:SOME_SYMBOL"
        )

    def test_unknown_exchange_prefix_passthrough(self) -> None:
        """A symbol with an unrecognised prefix (e.g. MCX_) is returned unchanged."""
        assert GrowwBrokerService._to_colon_format("MCX_GOLD") == "MCX_GOLD"
