"""Tests for RedisCallSessionRepository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

import pytest

from api_gateway.app.adapters.outbound.voice.redis_call_session_repository import (
    RedisCallSessionRepository,
)
from api_gateway.app.domain.models.call_session import CallSession

pytestmark = pytest.mark.anyio


class FakeRedisClient:
    """Minimal in-memory stand-in for redis.asyncio.Redis, only what
    RedisCallSessionRepository uses.
    """

    def __init__(self) -> None:
        self.store: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}

    async def set(self, key: str, value: str, *, ex: Optional[int] = None) -> None:
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def get(self, key: str) -> Optional[str]:
        return self.store.get(key)

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)
        self.ttls.pop(key, None)


def _session(**overrides) -> CallSession:
    defaults = dict(
        call_sid="CA123",
        channel_connection_id=uuid4(),
        project_id=uuid4(),
        agent_id=uuid4(),
        langflow_flow_id="flow-1",
        from_number="+15550001111",
        to_number="+15559998888",
        provider="twilio",
        status="ringing",
        started_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CallSession(**defaults)


async def test_save_then_get_round_trips_the_session():
    client = FakeRedisClient()
    repo = RedisCallSessionRepository(client)
    session = _session()

    await repo.save(session, ttl_seconds=3600)
    fetched = await repo.get("CA123")

    assert fetched == session


async def test_save_sets_the_configured_ttl():
    client = FakeRedisClient()
    repo = RedisCallSessionRepository(client)

    await repo.save(_session(), ttl_seconds=1800)

    assert client.ttls["voice:call_session:CA123"] == 1800


async def test_get_returns_none_for_unknown_call_sid():
    client = FakeRedisClient()
    repo = RedisCallSessionRepository(client)

    assert await repo.get("unknown") is None


async def test_delete_removes_the_session():
    client = FakeRedisClient()
    repo = RedisCallSessionRepository(client)
    await repo.save(_session(), ttl_seconds=3600)

    await repo.delete("CA123")

    assert await repo.get("CA123") is None
