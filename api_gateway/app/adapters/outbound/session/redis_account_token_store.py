"""Redis implementation of AccountTokenStorePort.

Same shape and guarantees as `redis_sso_ticket_store.py` (opaque token,
key = prefix + SHA-256(token), single-use via GETDEL), kept as a separate
file rather than a shared helper so a change here can never affect the
Langflow SSO ticket flow, and vice versa. Two instances of this class
(different `prefix`) back account activation and password reset, so a
token issued for one can never be redeemed as the other.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional
from uuid import UUID

from redis.asyncio import Redis


class RedisAccountTokenStore:
    """Single-use tokens stored as `<prefix><sha256> -> user_id` with a TTL."""

    def __init__(self, client: Redis, *, prefix: str) -> None:
        """Build the store.

        Args:
            client (Redis): An async Redis client (`decode_responses=True`).
            prefix (str): Namespaces this store's keys, e.g. `auth:activate:`
                or `auth:reset:` - keeps the two token kinds from colliding
                or being redeemable as one another.
        """
        self._client = client
        self._prefix = prefix

    def _key(self, token: str) -> str:
        """Redis key for a token: its SHA-256, so a Redis leak yields no usable tokens."""
        return self._prefix + hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def issue(self, user_id: UUID, *, ttl_seconds: int) -> str:
        """Create a token for a user.

        Args:
            user_id (UUID): The user the token is for.
            ttl_seconds (int): Lifetime.

        Returns:
            str: A 256-bit random opaque token (URL-safe).
        """
        token = secrets.token_urlsafe(32)
        await self._client.set(self._key(token), str(user_id), ex=ttl_seconds)
        return token

    async def redeem(self, token: str) -> Optional[UUID]:
        """Consume a token atomically (GETDEL: two concurrent redeems cannot both win).

        Args:
            token (str): The value presented by the browser.

        Returns:
            Optional[UUID]: The user it was issued for, or None if unknown,
            already used or expired.
        """
        if not token:
            return None
        raw = await self._client.getdel(self._key(token))
        return UUID(raw) if raw else None
