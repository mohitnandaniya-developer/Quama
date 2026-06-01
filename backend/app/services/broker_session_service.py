"""Broker session lifecycle helpers for Angel One authentication."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.cache_keys import (
    broker_jwt_key,
    portfolio_snapshot_key,
)
from app.core.encryption import decrypt, encrypt
from app.core.exceptions import (
    BrokerAuthError,
    BrokerNotConfiguredError,
    BrokerRefreshError,
    BrokerSessionNotFoundError,
    BrokerTotpError,
)
from app.integrations.angel_one.sdk import (
    create_smart_connect,
    ensure_angel_one_configured,
    extract_optional_string,
    extract_required_string,
    extract_response_data,
    map_broker_auth_error,
)
from app.models.broker_session import BrokerSession
from app.schemas.broker import BrokerConnectResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)

ANGEL_ONE_BROKER = "angel_one"
GROWW_BROKER = "groww"
JWT_TTL_SECONDS = 82_800
REFRESH_WINDOW = timedelta(hours=23)
EXPIRY_WINDOW = timedelta(hours=22)


class BrokerSessionService:
    """Manage broker sessions, encrypted tokens, and JWT refresh."""

    _refresh_gate = asyncio.Lock()
    _refresh_locks: dict[str, asyncio.Lock] = {}

    def __init__(
        self,
        *,
        session: AsyncSession,
        cache_service: CacheService,
        settings: Settings,
    ) -> None:
        self.session = session
        self.cache_service = cache_service
        self.settings = settings

    async def connect_angel_one(
        self,
        *,
        user_id: str,
        client_code: str,
        password: str,
        totp: str,
    ) -> BrokerConnectResponse:
        """Authenticate with Angel One and persist an active session."""
        ensure_angel_one_configured(self.settings)
        client = self._create_angel_one_client()

        try:
            session_payload = await asyncio.wait_for(
                asyncio.to_thread(
                    client.generateSession,
                    client_code,
                    password,
                    totp,
                ),
                timeout=30.0,  # 30s timeout for Angel One auth
            )
        except TimeoutError:
            logger.warning(
                "Angel One generateSession timed out for user %s",
                user_id,
            )
            raise BrokerAuthError(
                "Angel One authentication timed out. Please try again."
            ) from None
        except Exception as exc:  # pragma: no cover - depends on SDK/network.
            raise map_broker_auth_error(exc) from exc

        session_data = extract_response_data(session_payload)
        jwt_token = extract_required_string(
            session_data,
            ("jwtToken", "jwt_token"),
            fallback="jwt token",
        )
        refresh_token = extract_required_string(
            session_data,
            ("refreshToken", "refresh_token"),
            fallback="refresh token",
        )
        feed_token = extract_optional_string(
            session_data,
            ("feedToken", "feed_token"),
        )
        resolved_client_code = (
            extract_optional_string(session_data, ("clientcode", "clientCode"))
            or client_code.strip()
        )

        broker_session = await self._get_or_create_session(
            user_id=user_id,
            broker=ANGEL_ONE_BROKER,
        )
        now = datetime.now(UTC)
        broker_session.client_code = resolved_client_code
        broker_session.jwt_token = encrypt(jwt_token)
        broker_session.refresh_token = encrypt(refresh_token)
        broker_session.feed_token = feed_token
        broker_session.is_active = True
        broker_session.connected_at = now
        broker_session.token_refreshed_at = now
        broker_session.expires_at = now + timedelta(hours=24)

        await self.session.commit()
        await self.session.refresh(broker_session)

        await self.cache_service.set(
            broker_jwt_key(user_id=user_id, broker=ANGEL_ONE_BROKER),
            jwt_token,
            self._jwt_ttl_seconds(),
        )
        await self._delete_dependent_cache_keys(
            user_id=user_id,
            broker=ANGEL_ONE_BROKER,
        )

        return BrokerConnectResponse(
            broker=broker_session.broker,
            client_code=broker_session.client_code,
            connected=True,
            connected_at=broker_session.connected_at,
        )

    async def connect_groww(
        self,
        *,
        user_id: str,
        api_key: str,
        totp: str,
    ) -> BrokerConnectResponse:
        """Authenticate with Groww using the TOTP flow and persist a session."""
        resolved_api_key = api_key.strip()
        resolved_totp = totp.strip()
        if not resolved_api_key:
            raise BrokerAuthError("Groww API key is required.")
        if not resolved_totp:
            raise BrokerTotpError("Groww TOTP is required.")

        token_payload = await self._request_groww_access_token(
            api_key=resolved_api_key,
            totp=resolved_totp,
        )
        jwt_token = self._extract_groww_access_token(token_payload)
        expires_at = self._extract_groww_expiry(token_payload)
        resolved_client_code = self._mask_secret(resolved_api_key)

        broker_session = await self._get_or_create_session(
            user_id=user_id,
            broker=GROWW_BROKER,
        )
        now = datetime.now(UTC)
        broker_session.client_code = resolved_client_code
        broker_session.jwt_token = encrypt(jwt_token)
        broker_session.refresh_token = encrypt("")
        broker_session.feed_token = None
        broker_session.is_active = True
        broker_session.connected_at = now
        broker_session.token_refreshed_at = now
        broker_session.expires_at = expires_at

        await self.session.commit()
        await self.session.refresh(broker_session)

        await self.cache_service.set(
            broker_jwt_key(user_id=user_id, broker=GROWW_BROKER),
            jwt_token,
            self._jwt_ttl_seconds(),
        )
        await self._delete_dependent_cache_keys(
            user_id=user_id,
            broker=GROWW_BROKER,
        )

        return BrokerConnectResponse(
            broker=broker_session.broker,
            client_code=broker_session.client_code,
            connected=True,
            connected_at=broker_session.connected_at,
        )

    async def _request_groww_access_token(
        self,
        *,
        api_key: str,
        totp: str,
    ) -> Any:
        """Request a Groww access token through the official Python SDK."""
        groww_api = self._get_groww_api_class()
        try:
            return await asyncio.to_thread(
                groww_api.get_access_token,
                api_key=api_key,
                totp=totp,
            )
        except BrokerNotConfiguredError:
            raise
        except Exception as exc:
            message = str(exc)
            if "totp" in message.lower():
                raise BrokerTotpError(message or "Wrong Groww TOTP.") from exc
            raise BrokerAuthError(message or "Groww authentication failed.") from exc

    async def disconnect(self, *, user_id: str, broker: str) -> None:
        """Deactivate a broker session and clear dependent caches."""
        broker_session = await self.get_active_session(user_id=user_id, broker=broker)
        if broker_session is None:
            raise BrokerSessionNotFoundError()

        if broker == ANGEL_ONE_BROKER:
            ensure_angel_one_configured(self.settings)
            try:
                client = self._create_angel_one_client()
                await asyncio.to_thread(
                    client.terminateSession,
                    broker_session.client_code,
                )
            except Exception as exc:
                logger.warning(
                    "Angel One terminateSession failed for user %s: %s",
                    user_id,
                    exc,
                    exc_info=False,
                )

        broker_session.is_active = False
        broker_session.jwt_token = ""
        broker_session.refresh_token = ""
        broker_session.feed_token = None
        broker_session.token_refreshed_at = None
        broker_session.expires_at = None
        await self.session.commit()

        await self.cache_service.delete(broker_jwt_key(user_id=user_id, broker=broker))
        await self._delete_dependent_cache_keys(user_id=user_id, broker=broker)

    async def get_active_session(
        self,
        *,
        user_id: str,
        broker: str,
    ) -> BrokerSession | None:
        """Return an active broker session if one exists."""
        stmt = select(BrokerSession).where(
            BrokerSession.user_id == user_id,
            BrokerSession.broker == broker,
            BrokerSession.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        broker_session = result.scalar_one_or_none()
        await self._release_read_transaction()
        return broker_session

    async def list_active_sessions(self, *, user_id: str) -> list[BrokerSession]:
        """Return all active broker sessions for a user."""
        stmt = (
            select(BrokerSession)
            .where(
                BrokerSession.user_id == user_id,
                BrokerSession.is_active.is_(True),
            )
            .order_by(BrokerSession.connected_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        await self._release_read_transaction()
        return rows

    async def get_jwt(self, *, user_id: str, broker: str) -> str:
        """Return a current broker JWT, preferring Redis over the database."""
        cache_key = broker_jwt_key(user_id=user_id, broker=broker)
        cached = await self.cache_service.get(cache_key)
        if isinstance(cached, str) and cached.strip():
            broker_session = await self.get_active_session(
                user_id=user_id,
                broker=broker,
            )
            if broker_session is None:
                await self.cache_service.delete(cache_key)
                raise BrokerSessionNotFoundError()
            await self._raise_if_non_refreshable_session_expired(
                broker_session=broker_session,
                user_id=user_id,
                broker=broker,
            )
            if broker != ANGEL_ONE_BROKER:
                return cached
            if self._should_refresh_token(broker_session):
                return await self.refresh_token_if_needed(
                    user_id=user_id,
                    broker=broker,
                )
            return cached

        broker_session = await self.get_active_session(user_id=user_id, broker=broker)
        if broker_session is None:
            raise BrokerSessionNotFoundError()

        await self._raise_if_non_refreshable_session_expired(
            broker_session=broker_session,
            user_id=user_id,
            broker=broker,
        )
        if broker != ANGEL_ONE_BROKER:
            jwt_token = decrypt(broker_session.jwt_token)
            if not jwt_token.strip():
                raise BrokerSessionNotFoundError()
            await self.cache_service.set(cache_key, jwt_token, self._jwt_ttl_seconds())
            return jwt_token

        if self._should_refresh_token(broker_session):
            return await self.refresh_token_if_needed(user_id=user_id, broker=broker)

        jwt_token = decrypt(broker_session.jwt_token)
        if not jwt_token.strip():
            raise BrokerSessionNotFoundError()

        await self.cache_service.set(cache_key, jwt_token, self._jwt_ttl_seconds())
        return jwt_token

    async def refresh_token_if_needed(
        self,
        *,
        user_id: str,
        broker: str,
        force: bool = False,
    ) -> str:
        """Refresh a broker JWT if the token is stale."""
        refresh_lock = await self._get_refresh_lock(user_id=user_id, broker=broker)
        async with refresh_lock:
            return await self._refresh_token_locked(
                user_id=user_id,
                broker=broker,
                force=force,
            )

    async def _refresh_token_locked(
        self,
        *,
        user_id: str,
        broker: str,
        force: bool = False,
        broker_session: BrokerSession | None = None,
    ) -> str:
        """Refresh a broker JWT while holding a user+broker refresh lock."""
        broker_session = broker_session or await self.get_active_session(
            user_id=user_id,
            broker=broker,
        )
        if broker_session is None:
            raise BrokerSessionNotFoundError()

        if not force and not self._should_refresh_token(broker_session):
            jwt_token = decrypt(broker_session.jwt_token)
            await self.cache_service.set(
                broker_jwt_key(user_id=user_id, broker=broker),
                jwt_token,
                self._jwt_ttl_seconds(),
            )
            return jwt_token

        if broker != ANGEL_ONE_BROKER:
            raise BrokerRefreshError("Broker refresh is not supported.")

        ensure_angel_one_configured(self.settings)
        client = self._create_angel_one_client()
        refresh_token = decrypt(broker_session.refresh_token)

        try:
            payload = await asyncio.to_thread(client.generateToken, refresh_token)
            token_data = extract_response_data(payload)
        except BrokerAuthError as exc:
            if "invalid token" in str(exc).lower():
                await self._invalidate_broker_session(
                    broker_session=broker_session,
                    user_id=user_id,
                    broker=broker,
                )
                raise BrokerSessionNotFoundError(
                    "Broker session expired. Please reconnect your broker."
                ) from exc
            await self._invalidate_cache_only(user_id=user_id, broker=broker)
            raise BrokerRefreshError() from exc
        except Exception as exc:  # pragma: no cover - depends on SDK/network.
            if "invalid token" in str(exc).lower():
                await self._invalidate_broker_session(
                    broker_session=broker_session,
                    user_id=user_id,
                    broker=broker,
                )
                raise BrokerSessionNotFoundError(
                    "Broker session expired. Please reconnect your broker."
                ) from exc
            await self._invalidate_cache_only(user_id=user_id, broker=broker)
            raise BrokerRefreshError() from exc

        jwt_token = extract_required_string(
            token_data,
            ("jwtToken", "jwt_token"),
            fallback="jwt token",
        )
        maybe_refresh_token = extract_optional_string(
            token_data,
            ("refreshToken", "refresh_token"),
        )
        maybe_feed_token = extract_optional_string(
            token_data,
            ("feedToken", "feed_token"),
        )

        broker_session.jwt_token = encrypt(jwt_token)
        if maybe_refresh_token:
            broker_session.refresh_token = encrypt(maybe_refresh_token)
        if maybe_feed_token is not None:
            broker_session.feed_token = maybe_feed_token
        broker_session.token_refreshed_at = datetime.now(UTC)
        broker_session.expires_at = broker_session.token_refreshed_at + timedelta(
            hours=24
        )

        await self.session.commit()
        await self.cache_service.set(
            broker_jwt_key(user_id=user_id, broker=broker),
            jwt_token,
            self._jwt_ttl_seconds(),
        )
        await self._delete_dependent_cache_keys(user_id=user_id, broker=broker)
        return jwt_token

    async def _refresh_session_token_if_needed(
        self,
        *,
        broker_session: BrokerSession,
        force: bool = False,
    ) -> str:
        """Refresh an already-loaded broker session without querying it again."""
        user_id = broker_session.user_id
        broker = broker_session.broker
        refresh_lock = await self._get_refresh_lock(user_id=user_id, broker=broker)
        async with refresh_lock:
            return await self._refresh_token_locked(
                user_id=user_id,
                broker=broker,
                force=force,
                broker_session=broker_session,
            )

    async def _invalidate_broker_session(
        self,
        *,
        broker_session: BrokerSession,
        user_id: str,
        broker: str,
    ) -> None:
        broker_session.is_active = False
        broker_session.jwt_token = ""
        broker_session.refresh_token = ""
        broker_session.feed_token = None
        broker_session.token_refreshed_at = None
        broker_session.expires_at = None
        await self.session.commit()
        await self.cache_service.delete(broker_jwt_key(user_id=user_id, broker=broker))
        await self._delete_dependent_cache_keys(user_id=user_id, broker=broker)

    async def _invalidate_cache_only(self, *, user_id: str, broker: str) -> None:
        await self.cache_service.delete(broker_jwt_key(user_id=user_id, broker=broker))
        await self._delete_dependent_cache_keys(user_id=user_id, broker=broker)

    async def invalidate_session(self, *, user_id: str, broker: str) -> None:
        """Deactivate a broker session without calling broker-side logout APIs."""
        broker_session = await self.get_active_session(user_id=user_id, broker=broker)
        if broker_session is not None:
            await self._invalidate_broker_session(
                broker_session=broker_session,
                user_id=user_id,
                broker=broker,
            )

    async def _raise_if_non_refreshable_session_expired(
        self,
        *,
        broker_session: BrokerSession,
        user_id: str,
        broker: str,
    ) -> None:
        if broker == ANGEL_ONE_BROKER:
            return

        if self._is_non_refreshable_session_expired(broker_session):
            await self._invalidate_broker_session(
                broker_session=broker_session,
                user_id=user_id,
                broker=broker,
            )
            raise BrokerSessionNotFoundError(
                "Broker session expired. Please reconnect your broker."
            )

    def _create_angel_one_client(self):
        return create_smart_connect(self.settings)

    @staticmethod
    def _get_groww_api_class() -> Any:
        try:
            from growwapi import GrowwAPI
        except ImportError as exc:
            raise BrokerNotConfiguredError(
                "Groww Python SDK is not installed."
            ) from exc
        return GrowwAPI

    async def _get_or_create_session(
        self,
        *,
        user_id: str,
        broker: str,
    ) -> BrokerSession:
        """Get or create a broker session."""
        stmt = select(BrokerSession).where(
            BrokerSession.user_id == user_id,
            BrokerSession.broker == broker,
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing

        broker_session = BrokerSession(
            user_id=user_id,
            broker=broker,
            client_code="",
            jwt_token="",
            refresh_token="",
            feed_token=None,
            is_active=True,
        )
        self.session.add(broker_session)
        await self.session.flush()
        return broker_session

    def _should_refresh_token(self, broker_session: BrokerSession) -> bool:
        refreshed_at = broker_session.token_refreshed_at or broker_session.connected_at
        normalized = self._ensure_utc_datetime(refreshed_at)
        return normalized <= datetime.now(UTC) - REFRESH_WINDOW

    def _is_non_refreshable_session_expired(
        self,
        broker_session: BrokerSession,
    ) -> bool:
        if broker_session.expires_at is not None:
            return self._ensure_utc_datetime(broker_session.expires_at) <= datetime.now(
                UTC
            )
        return self._should_refresh_token(broker_session)

    async def _delete_dependent_cache_keys(self, *, user_id: str, broker: str) -> None:
        if broker != ANGEL_ONE_BROKER:
            return
        await self.cache_service.delete(portfolio_snapshot_key(user_id=user_id))

    async def _release_read_transaction(self) -> None:
        """Return read-only database connections before slow broker API calls."""
        if self.session.in_transaction():
            await self.session.commit()

    def _jwt_ttl_seconds(self) -> int:
        """Return the configured broker JWT cache TTL."""
        return max(int(self.settings.broker_jwt_cache_ttl_seconds), 1)

    @staticmethod
    def _ensure_utc_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _extract_groww_access_token(payload: Any) -> str:
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if not isinstance(payload, dict):
            raise BrokerAuthError("Groww response did not include an access token.")
        token = BrokerSessionService._pick_string(
            payload,
            ("token", "access_token", "accessToken"),
        )
        if token is None and isinstance(payload.get("payload"), dict):
            token = BrokerSessionService._pick_string(
                payload["payload"],
                ("token", "access_token", "accessToken"),
            )
        if token is None:
            raise BrokerAuthError("Groww response did not include an access token.")
        return token

    @staticmethod
    def _extract_groww_expiry(payload: Any) -> datetime:
        if not isinstance(payload, dict):
            return datetime.now(UTC) + timedelta(hours=24)
        expiry = BrokerSessionService._pick_string(payload, ("expiry", "expires_at"))
        if expiry is None and isinstance(payload.get("payload"), dict):
            expiry = BrokerSessionService._pick_string(
                payload["payload"],
                ("expiry", "expires_at"),
            )
        if expiry is None:
            return datetime.now(UTC) + timedelta(hours=24)

        normalized = expiry.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.now(UTC) + timedelta(hours=24)
        return BrokerSessionService._ensure_utc_datetime(parsed)

    @staticmethod
    def _pick_string(source: dict[str, Any], keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _mask_secret(value: str) -> str:
        stripped = value.strip()
        if len(stripped) <= 4:
            return "API ****"
        return f"API ...{stripped[-4:]}"

    @classmethod
    async def _get_refresh_lock(cls, *, user_id: str, broker: str) -> asyncio.Lock:
        lock_key = f"{user_id}:{broker}"
        async with cls._refresh_gate:
            lock = cls._refresh_locks.get(lock_key)
            if lock is None:
                lock = asyncio.Lock()
                cls._refresh_locks[lock_key] = lock
            return lock


async def refresh_all_expiring_tokens(
    session: AsyncSession,
    cache_service: CacheService,
    settings: Settings,
) -> None:
    """Refresh all broker sessions older than the proactive refresh cutoff."""
    cutoff = datetime.now(UTC) - EXPIRY_WINDOW
    stmt = select(BrokerSession).where(
        BrokerSession.is_active.is_(True),
        or_(
            BrokerSession.token_refreshed_at.is_(None),
            BrokerSession.token_refreshed_at < cutoff,
        ),
    )
    rows = (await session.execute(stmt)).scalars().all()
    if session.in_transaction():
        await session.commit()

    for row in rows:
        if row.broker != ANGEL_ONE_BROKER:
            continue
        service = BrokerSessionService(
            session=session,
            cache_service=cache_service,
            settings=settings,
        )
        try:
            await service._refresh_session_token_if_needed(
                broker_session=row,
            )
        except Exception:
            logger.exception(
                "Failed to refresh broker token for user %s broker %s.",
                row.user_id,
                row.broker,
            )
