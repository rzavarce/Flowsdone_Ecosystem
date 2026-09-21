"""Redis implementation of AuthSessionRepositoryPort."""

from __future__ import annotations

import hashlib
import secrets
from typing import Optional
from uuid import UUID

from redis.asyncio import Redis

_SESSION_PREFIX = "auth:session:"
_USER_PREFIX = "auth:user_sessions:"


def _digest(token: str) -> str:
    """SHA-256 of a token: what is stored instead of the token itself, so
    a Redis leak does not hand out usable sessions."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RedisAuthSessionRepository:
    """Stores console sessions as `auth:session:<sha256(token)> -> user_id`
    with a sliding TTL, plus an `auth:user_sessions:<user_id>` set so all
    of a user's sessions can be revoked at once.
    """

    def __init__(self, client: Redis) -> None:
        """Build the repository.

        Args:
            client (Redis): An async Redis client (`decode_responses=True`).
        """
        self._client = client

    async def create(self, user_id: UUID, *, ttl_seconds: int) -> str:
        """Open a session.

        Args:
            user_id (UUID): Owner of the session.
            ttl_seconds (int): Idle lifetime.

        Returns:
            str: A 256-bit random opaque token (URL-safe).
        """
        token = secrets.token_urlsafe(32)
        key = _digest(token)
        await self._client.set(_SESSION_PREFIX + key, str(user_id), ex=ttl_seconds)
        await self._client.sadd(_USER_PREFIX + str(user_id), key)
        await self._client.expire(_USER_PREFIX + str(user_id), ttl_seconds)
        return token

    async def get_user_id(self, token: str, *, ttl_seconds: int) -> Optional[UUID]:
        """Resolve a token to its user and slide the expiry forward.

        Args:
            token (str): Token presented by the client.
            ttl_seconds (int): New idle lifetime.

        Returns:
            Optional[UUID]: The owner, or None if unknown or expired.
        """
        if not token:
            return None
        key = _SESSION_PREFIX + _digest(token)
        raw = await self._client.get(key)
        if raw is None:
            return None
        await self._client.expire(key, ttl_seconds)
        await self._client.expire(_USER_PREFIX + raw, ttl_seconds)
        return UUID(raw)

    async def delete(self, token: str) -> None:
        """Close a session (idempotent).

        Args:
            token (str): Token to invalidate.
        """
        if not token:
            return
        key = _digest(token)
        raw = await self._client.get(_SESSION_PREFIX + key)
        await self._client.delete(_SESSION_PREFIX + key)
        if raw is not None:
            await self._client.srem(_USER_PREFIX + raw, key)

    async def delete_all_for_user(self, user_id: UUID) -> None:
        """Close every session of a user.

        Args:
            user_id (UUID): Owner whose sessions are closed.
        """
        set_key = _USER_PREFIX + str(user_id)
        for key in await self._client.smembers(set_key):
            await self._client.delete(_SESSION_PREFIX + key)
        await self._client.delete(set_key)
