"""Clerk session-token verification helpers.

Verification accepts a configured PEM public key first, then a configured JWKS
URL, then a JWKS URL inferred from the token issuer. Tokens must be RS256,
signature-valid, time-valid, issuer-valid when configured, and authorized-party
valid when configured.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.config import Settings
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)
JWKS_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
CLOCK_SKEW_SECONDS = 60


class ClerkAuthService:
    """Verify Clerk session JWTs and resolve their stable Clerk user id."""

    def __init__(self, *, settings: Settings) -> None:
        self.settings = settings

    async def verify_token(self, token: str) -> str:
        """Return the Clerk user id from a verified session token."""
        try:
            header, payload, signing_input, signature = self._decode_token(token)
            if header.get("alg") != "RS256":
                raise AuthenticationError("Invalid authentication token.")

            public_key = await self._resolve_public_key(header=header, payload=payload)
            public_key.verify(
                signature,
                signing_input,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            self._validate_claims(payload)
        except AuthenticationError:
            logger.warning("JWT verification failed.")
            raise
        except (
            InvalidSignature,
            ValueError,
            TypeError,
            KeyError,
            json.JSONDecodeError,
            httpx.HTTPError,
        ):
            logger.warning("JWT verification failed.", exc_info=True)
            raise AuthenticationError("Invalid authentication token.") from None

        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            raise AuthenticationError("Invalid authentication token.")
        return user_id.strip()

    def _decode_token(
        self,
        token: str,
    ) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid authentication token.")

        header_segment, payload_segment, signature_segment = parts
        header = json.loads(_base64url_decode(header_segment))
        payload = json.loads(_base64url_decode(payload_segment))
        signature = _base64url_decode(signature_segment)
        signing_input = f"{header_segment}.{payload_segment}".encode()

        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise AuthenticationError("Invalid authentication token.")

        return header, payload, signing_input, signature

    async def _resolve_public_key(
        self,
        *,
        header: dict[str, Any],
        payload: dict[str, Any],
    ):
        configured_key = self.settings.clerk_jwt_key.strip()
        if configured_key:
            return serialization.load_pem_public_key(
                configured_key.replace("\\n", "\n").encode()
            )

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthenticationError("Invalid authentication token.")

        jwks = await self._get_jwks(payload=payload)
        for key in jwks.get("keys", []):
            if not isinstance(key, dict):
                continue
            if key.get("kid") == kid:
                return _jwk_to_public_key(key)

        raise AuthenticationError("Invalid authentication token.")

    async def _get_jwks(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        jwks_url = self.settings.clerk_jwks_url.strip()
        if not jwks_url:
            issuer = str(payload.get("iss") or "").rstrip("/")
            if not issuer.startswith("https://"):
                raise AuthenticationError("Clerk JWKS URL is not configured.")
            jwks_url = f"{issuer}/.well-known/jwks.json"

        now = time.time()
        cached = JWKS_CACHE.get(jwks_url)
        if cached and cached[0] > now:
            return cached[1]

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks = response.json()

        if not isinstance(jwks, dict):
            raise AuthenticationError("Invalid Clerk JWKS response.")

        ttl = max(self.settings.clerk_jwks_cache_ttl_seconds, 1)
        JWKS_CACHE[jwks_url] = (now + ttl, jwks)
        return jwks

    def _validate_claims(self, payload: dict[str, Any]) -> None:
        now = int(time.time())
        exp = payload.get("exp")
        if not isinstance(exp, int) or exp <= now - CLOCK_SKEW_SECONDS:
            raise AuthenticationError("Authentication token has expired.")

        nbf = payload.get("nbf")
        if isinstance(nbf, int) and nbf > now + CLOCK_SKEW_SECONDS:
            raise AuthenticationError("Authentication token is not active yet.")

        issuer = self.settings.clerk_issuer.strip().rstrip("/")
        if issuer and payload.get("iss") != issuer:
            raise AuthenticationError("Invalid authentication token issuer.")

        authorized_parties = self.settings.clerk_authorized_parties
        if authorized_parties and payload.get("azp") not in authorized_parties:
            raise AuthenticationError("Invalid authentication token audience.")


def _base64url_decode(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(f"{value}{'=' * padding_length}")


def _jwk_to_public_key(key: dict[str, Any]):
    if key.get("kty") != "RSA":
        raise AuthenticationError("Invalid Clerk JWKS key.")
    if key.get("alg") not in {None, "RS256"}:
        raise AuthenticationError("Invalid Clerk JWKS key.")

    modulus = int.from_bytes(_base64url_decode(str(key["n"])), "big")
    exponent = int.from_bytes(_base64url_decode(str(key["e"])), "big")
    return rsa.RSAPublicNumbers(exponent, modulus).public_key()
