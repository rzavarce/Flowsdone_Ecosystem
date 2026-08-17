"""Redis implementation of SessionRepositoryPort."""

from __future__ import annotations

import logging
from typing import Optional

from redis.asyncio import Redis

from api_gateway.app.domain.models.session import Session
from api_gateway.app.domain.ports.outbound import SessionRepositoryPort

logger = logging.getLogger("switchboard.session_repository")

_KEY_PREFIX = "switchboard:session:"


class RedisSessionRepository(SessionRepositoryPort):
    """Stores Session as TTL-backed JSON in Redis, keyed by conversation id.

    Mirrors adapters/outbound/voice/redis_call_session_repository.py -
    same storage shape, same rationale (fast, ephemeral state read/
    written on every turn; the durable record lives in Postgres via
    SessionHistoryRepositoryPort).
    """

    def __init__(self, client: Redis) -> None:
        """Build the repository.

        Args:
            client (Redis): An async Redis client.
        """
        self._client = client

    async def get(self, session_id: str) -> Optional[Session]:
        """Fetch a session by id.

        Args:
            session_id (str): Conversation id.

        Returns:
            Optional[Session]: The session, or None if it does not
            exist or has expired.
        """
        raw = await self._client.get(_key(session_id))
        if raw is None:
            return None
        return Session.model_validate_json(raw)

    async def save(self, session: Session, *, ttl_seconds: int) -> None:
        """Persist a session, expiring it after `ttl_seconds` of inactivity.

        Args:
            session (Session): The session to store.
            ttl_seconds (int): Seconds after which the entry expires if
                untouched.
        """
        await self._client.set(_key(session.id), session.model_dump_json(), ex=ttl_seconds)
        logger.info("switchboard.session.saved", extra={"session_id": session.id})

    async def delete(self, session_id: str) -> None:
        """Remove a session.

        Args:
            session_id (str): Conversation id.
        """
        await self._client.delete(_key(session_id))
        logger.info("switchboard.session.deleted", extra={"session_id": session_id})


def _key(session_id: str) -> str:
    """Build the Redis key for a session.

    Args:
        session_id (str): Conversation id.

    Returns:
        str: The namespaced Redis key.
    """
    return f"{_KEY_PREFIX}{session_id}"
