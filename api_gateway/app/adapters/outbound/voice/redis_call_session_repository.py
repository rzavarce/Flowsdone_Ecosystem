"""Redis implementation of CallSessionRepositoryPort."""

from __future__ import annotations

import logging
from typing import Optional

from redis.asyncio import Redis

from ....domain.models.call_session import CallSession
from ....domain.ports.outbound import CallSessionRepositoryPort

logger = logging.getLogger("channels.voice.call_session_repository")

_KEY_PREFIX = "voice:call_session:"


class RedisCallSessionRepository(CallSessionRepositoryPort):
    """Stores CallSession as TTL-backed JSON in Redis, keyed by call_sid.

    Redis (rather than Postgres) because this is short-lived, best-effort
    context needed only to bridge the TwiML webhook request and the
    streaming WebSocket request that follows it moments later - not a
    durable record of the call.
    """

    def __init__(self, client: Redis) -> None:
        """Build the repository.

        Args:
            client (Redis): An async Redis client.
        """
        self._client = client

    async def save(self, session: CallSession, *, ttl_seconds: int) -> None:
        """Persist a call session, expiring it after `ttl_seconds`.

        Args:
            session (CallSession): The call session to store.
            ttl_seconds (int): Seconds after which the entry expires.
        """
        await self._client.set(_key(session.call_sid), session.model_dump_json(), ex=ttl_seconds)
        logger.info("call_session.saved", extra={"call_sid": session.call_sid})

    async def get(self, call_sid: str) -> Optional[CallSession]:
        """Fetch a call session by its call_sid.

        Args:
            call_sid (str): Provider-assigned unique id for the call.

        Returns:
            Optional[CallSession]: The call session, or None if it does
            not exist or has expired.
        """
        raw = await self._client.get(_key(call_sid))
        if raw is None:
            return None
        return CallSession.model_validate_json(raw)

    async def delete(self, call_sid: str) -> None:
        """Remove a call session.

        Args:
            call_sid (str): Provider-assigned unique id for the call.
        """
        await self._client.delete(_key(call_sid))
        logger.info("call_session.deleted", extra={"call_sid": call_sid})


def _key(call_sid: str) -> str:
    """Build the Redis key for a call session.

    Args:
        call_sid (str): Provider-assigned unique id for the call.

    Returns:
        str: The namespaced Redis key.
    """
    return f"{_KEY_PREFIX}{call_sid}"
