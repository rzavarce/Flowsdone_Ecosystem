"""Fernet-based encryption for channel/app credentials at rest."""

from __future__ import annotations

import json
from typing import Any, Dict

from cryptography.fernet import Fernet

from app.core.config import settings


def _fernet() -> Fernet:
    """Build a Fernet instance from the configured encryption key.

    Returns:
        Fernet: An instance ready to encrypt/decrypt.

    Raises:
        RuntimeError: If CHANNEL_CREDENTIALS_ENCRYPTION_KEY is not set.
    """
    if not settings.CHANNEL_CREDENTIALS_ENCRYPTION_KEY:
        raise RuntimeError("CHANNEL_CREDENTIALS_ENCRYPTION_KEY is not configured")

    return Fernet(settings.CHANNEL_CREDENTIALS_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_credentials(data: Dict[str, Any]) -> Dict[str, str]:
    """Encrypt a credentials dict for storage.

    Args:
        data (Dict[str, Any]): Plain-text credentials.

    Returns:
        Dict[str, str]: A dict with a single "ciphertext" key holding
        the encrypted, base64-encoded token.
    """
    token = _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")
    return {"ciphertext": token}


def decrypt_credentials(stored: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt a credentials dict previously produced by
    encrypt_credentials.

    Args:
        stored (Dict[str, Any]): The stored dict, expected to contain
            "ciphertext".

    Returns:
        Dict[str, Any]: The decrypted credentials, or an empty dict if
        no ciphertext is present.
    """
    token = stored.get("ciphertext")
    if not token:
        return {}

    raw = _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    return json.loads(raw)
