from __future__ import annotations

import json
from typing import Any, Dict

from cryptography.fernet import Fernet

from ....core.config import settings


def _fernet() -> Fernet:
    if not settings.CHANNEL_CREDENTIALS_ENCRYPTION_KEY:
        raise RuntimeError("CHANNEL_CREDENTIALS_ENCRYPTION_KEY is not configured")

    return Fernet(settings.CHANNEL_CREDENTIALS_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_credentials(data: Dict[str, Any]) -> Dict[str, str]:
    token = _fernet().encrypt(json.dumps(data).encode("utf-8")).decode("utf-8")
    return {"ciphertext": token}


def decrypt_credentials(stored: Dict[str, Any]) -> Dict[str, Any]:
    token = stored.get("ciphertext")
    if not token:
        return {}

    raw = _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    return json.loads(raw)
