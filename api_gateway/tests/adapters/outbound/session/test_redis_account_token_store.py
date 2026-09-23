"""Tests for RedisAccountTokenStore."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.adapters.outbound.session.redis_account_token_store import RedisAccountTokenStore
from api_gateway.tests.support.fakes import FakeRedisClient

pytestmark = pytest.mark.anyio


def _store(prefix: str = "auth:activate:"):
    client = FakeRedisClient()
    return RedisAccountTokenStore(client, prefix=prefix), client


async def test_a_token_returns_its_user_id_once():
    store, _ = _store()
    user_id = uuid4()
    token = await store.issue(user_id, ttl_seconds=86400)

    assert await store.redeem(token) == user_id
    assert await store.redeem(token) is None


async def test_tokens_are_unguessable_and_unique():
    store, _ = _store()
    a = await store.issue(uuid4(), ttl_seconds=86400)
    b = await store.issue(uuid4(), ttl_seconds=86400)
    assert a != b and len(a) >= 40


async def test_only_a_hash_is_stored_and_it_expires():
    store, client = _store()
    token = await store.issue(uuid4(), ttl_seconds=86400)

    assert all(token not in key for key in client.store)
    assert list(client.ttls.values()) == [86400]


async def test_unknown_and_empty_tokens_are_rejected():
    store, _ = _store()
    assert await store.redeem("nope") is None
    assert await store.redeem("") is None


async def test_activation_and_reset_stores_cannot_redeem_each_others_tokens():
    """Two instances (different prefixes) share the same Redis client, same
    as production: an activation token must not work as a reset token."""
    client = FakeRedisClient()
    activate = RedisAccountTokenStore(client, prefix="auth:activate:")
    reset = RedisAccountTokenStore(client, prefix="auth:reset:")
    token = await activate.issue(uuid4(), ttl_seconds=86400)

    assert await reset.redeem(token) is None
    assert len(client.store) == 1  # still there - reset() didn't consume it
