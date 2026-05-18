"""Authentication dependency tests."""

from __future__ import annotations

import base64
import json
import time
from typing import Annotated

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.core.error_handlers import register_exception_handlers
from app.dependencies import require_user_id


@pytest.mark.asyncio
async def test_clerk_bearer_token_resolves_user_id(test_settings: Settings) -> None:
    """A valid Clerk-style session JWT becomes the protected route user id."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings = test_settings.model_copy(
        update={
            "debug": False,
            "clerk_jwt_key": public_key.decode(),
            "clerk_issuer": "https://test.clerk.accounts.dev",
            "clerk_authorized_parties": ["http://localhost:3000"],
        }
    )
    token = _sign_test_token(
        private_key=private_key,
        payload={
            "sub": "user_123",
            "iss": "https://test.clerk.accounts.dev",
            "azp": "http://localhost:3000",
            "exp": int(time.time()) + 300,
        },
    )

    async with _auth_client(settings) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "user_123"}


@pytest.mark.asyncio
async def test_missing_auth_returns_401_when_debug_is_false(
    test_settings: Settings,
) -> None:
    """Production mode requires Clerk authentication."""
    settings = test_settings.model_copy(update={"debug": False})

    async with _auth_client(settings) as client:
        response = await client.get("/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401(test_settings: Settings) -> None:
    """Malformed bearer tokens are rejected instead of using the dev fallback."""
    settings = test_settings.model_copy(update={"debug": True})

    async with _auth_client(settings) as client:
        response = await client.get(
            "/protected",
            headers={
                "Authorization": "Bearer invalid-token",
                "X-User-Id": "debug-user",
            },
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_expired_bearer_token_returns_401(test_settings: Settings) -> None:
    """Expired Clerk tokens are rejected."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings = test_settings.model_copy(
        update={
            "debug": False,
            "clerk_jwt_key": public_key.decode(),
            "clerk_issuer": "https://test.clerk.accounts.dev",
            "clerk_authorized_parties": ["http://localhost:3000"],
        }
    )
    token = _sign_test_token(
        private_key=private_key,
        payload={
            "sub": "user_123",
            "iss": "https://test.clerk.accounts.dev",
            "azp": "http://localhost:3000",
            "exp": int(time.time()) - 120,
        },
    )

    async with _auth_client(settings) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_invalid_issuer_or_audience_returns_401(
    test_settings: Settings,
) -> None:
    """Issuer and authorized-party mismatches are rejected."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    settings = test_settings.model_copy(
        update={
            "debug": False,
            "clerk_jwt_key": public_key.decode(),
            "clerk_issuer": "https://test.clerk.accounts.dev",
            "clerk_authorized_parties": ["http://localhost:3000"],
        }
    )
    token = _sign_test_token(
        private_key=private_key,
        payload={
            "sub": "user_123",
            "iss": "https://wrong.clerk.accounts.dev",
            "azp": "http://evil.localhost:3000",
            "exp": int(time.time()) + 300,
        },
    )

    async with _auth_client(settings) as client:
        response = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_debug_mode_keeps_x_user_id_fallback(test_settings: Settings) -> None:
    """Local tests and development can still use the legacy user-id header."""
    settings = test_settings.model_copy(update={"debug": True})

    async with _auth_client(settings) as client:
        response = await client.get(
            "/protected",
            headers={"X-User-Id": "debug-user"},
        )

    assert response.status_code == 200
    assert response.json() == {"user_id": "debug-user"}


def _auth_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(
        user_id: Annotated[str, Depends(require_user_id)],
    ) -> dict[str, str]:
        return {"user_id": user_id}

    return app


def _auth_client(settings: Settings) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=_auth_app(settings)),
        base_url="http://testserver",
    )


def _sign_test_token(
    *,
    private_key: rsa.RSAPrivateKey,
    payload: dict[str, object],
) -> str:
    header = {"alg": "RS256", "typ": "JWT", "kid": "test-key"}
    encoded_header = _base64url(json.dumps(header).encode())
    encoded_payload = _base64url(json.dumps(payload).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    signature = private_key.sign(
        signing_input,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return f"{encoded_header}.{encoded_payload}.{_base64url(signature)}"


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
