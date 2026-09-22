"""Redis implementation of SsoTicketStorePort."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Dict, Optional

from redis.asyncio import Redis

_PREFIX = "langflow:sso:"


def _key(ticket: str) -> str:
    """Redis key for a ticket: its SHA-256, so a Redis leak yields no usable tickets."""
    return _PREFIX + hashlib.sha256(ticket.encode("utf-8")).hexdigest()


class RedisSsoTicketStore:
    """Single-use tickets stored as `langflow:sso:<sha256> -> json` with a TTL."""

    def __init__(self, client: Redis) -> None:
        """Build the store.

        Args:
            client (Redis): An async Redis client (`decode_responses=True`).
        """
        self._client = client

    async def issue(self, payload: Dict[str, str], *, ttl_seconds: int) -> str:
        """Create a ticket.

        Args:
            payload (Dict[str, str]): Data recovered on redeem.
            ttl_seconds (int): Lifetime.

        Returns:
            str: A 256-bit random opaque ticket (URL-safe).
        """
        ticket = secrets.token_urlsafe(32)
        await self._client.set(_key(ticket), json.dumps(payload), ex=ttl_seconds)
        return ticket

    async def redeem(self, ticket: str) -> Optional[Dict[str, str]]:
        """Consume a ticket atomically (GETDEL: two concurrent redeems cannot both win).

        Args:
            ticket (str): The value presented by the browser.

        Returns:
            Optional[Dict[str, str]]: The payload, or None if unknown, used or expired.
        """
        if not ticket:
            return None
        raw = await self._client.getdel(_key(ticket))
        return json.loads(raw) if raw else None
