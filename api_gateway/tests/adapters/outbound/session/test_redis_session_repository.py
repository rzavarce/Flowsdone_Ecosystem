"""Tests for RedisSessionRepository."""

from __future__ import annotations

import pytest

from app.adapters.outbound.session.redis_session_repository import (
    RedisSessionRepository,
)
from api_gateway.tests.support.fakes import FakeRedisClient, make_session

pytestmark = pytest.mark.anyio


async def test_save_then_get_round_trips_the_session():
    client = FakeRedisClient()
    repo = RedisSessionRepository(client)
    session = make_session(id="proj:telegram:chat-1")

    await repo.save(session, ttl_seconds=3600)
    fetched = await repo.get("proj:telegram:chat-1")

    assert fetched == session


async def test_save_sets_the_configured_ttl():
    client = FakeRedisClient()
    repo = RedisSessionRepository(client)

    await repo.save(make_session(id="proj:telegram:chat-1"), ttl_seconds=86400)

    assert client.ttls["switchboard:session:proj:telegram:chat-1"] == 86400


async def test_get_returns_none_for_unknown_session():
    client = FakeRedisClient()
    repo = RedisSessionRepository(client)

    assert await repo.get("unknown") is None


async def test_delete_removes_the_session():
    client = FakeRedisClient()
    repo = RedisSessionRepository(client)
    await repo.save(make_session(id="proj:telegram:chat-1"), ttl_seconds=3600)

    await repo.delete("proj:telegram:chat-1")

    assert await repo.get("proj:telegram:chat-1") is None
