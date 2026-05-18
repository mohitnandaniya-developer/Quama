"""Helpers for encrypting sensitive broker tokens."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _get_fernet() -> Fernet:
    secret = get_settings().broker_token_secret.strip()
    if not secret:
        msg = "BROKER_TOKEN_SECRET is required for broker token encryption."
        raise RuntimeError(msg)

    try:
        # Accept a pre-generated Fernet key, otherwise derive one from the secret.
        decoded = base64.urlsafe_b64decode(secret.encode("utf-8"))
        if len(decoded) == 32:
            fernet_key = secret.encode("utf-8")
        else:
            derived_key = hashlib.sha256(secret.encode("utf-8")).digest()
            fernet_key = base64.urlsafe_b64encode(derived_key)
        return Fernet(fernet_key)
    except Exception as exc:  # pragma: no cover - defensive config guard.
        msg = "BROKER_TOKEN_SECRET could not be converted to a valid Fernet key."
        raise RuntimeError(msg) from exc


def encrypt(value: str) -> str:
    """Encrypt a plaintext value for storage."""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(value: str) -> str:
    """Decrypt a previously encrypted value."""
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        msg = "Stored broker token could not be decrypted."
        raise RuntimeError(msg) from exc
