"""Fernet-based encrypt/decrypt helpers for storing sensitive tokens."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    """Derive a Fernet instance from the application secret key.

    We SHA-256 hash the secret key to get exactly 32 bytes, then base64url-encode
    it to produce the key format expected by Fernet.
    """
    raw = hashlib.sha256(settings.secret_key.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Encrypt *plaintext* and return a base64-encoded ciphertext string."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt *ciphertext* (produced by :func:`encrypt`) and return the plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
