"""Tests for RedisAuthSessionRepository."""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from app.adapters.outbound.session.redis_auth_session_repository import RedisAuthSessionRepository
from api_gateway.tests.support.fakes import FakeRedisClient

pytestmark = pytest.mark.anyio


def _repo():
    client = FakeRedisClient()
    return RedisAuthSessionRepository(client), client


async def test_create_returns_an_opaque_token_that_resolves_to_the_user():
    repo, _ = _repo()
    user_id = uuid4()

    token = await repo.create(user_id, ttl_seconds=60)

    assert len(token) >= 40
    assert await repo.get_user_id(token, ttl_seconds=60) == user_id


async def test_tokens_are_unique():
    repo, _ = _repo()
    user_id = uuid4()
    assert await repo.create(user_id, ttl_seconds=60) != await repo.create(user_id, ttl_seconds=60)


async def test_only_a_hash_of_the_token_is_stored():
    repo, client = _repo()
    token = await repo.create(uuid4(), ttl_seconds=60)

    stored = " ".join(list(client.store) + [m for s in client.sets.values() for m in s])
    assert token not in stored
    assert hashlib.sha256(token.encode()).hexdigest() in stored


async def test_session_gets_the_ttl_and_lookup_slides_it():
    repo, client = _repo()
    token = await repo.create(uuid4(), ttl_seconds=60)
    key = "auth:session:" + hashlib.sha256(token.encode()).hexdigest()
    assert client.ttls[key] == 60

    await repo.get_user_id(token, ttl_seconds=999)
    assert client.ttls[key] == 999


async def test_unknown_or_empty_token_resolves_to_none():
    repo, _ = _repo()
    assert await repo.get_user_id("nope", ttl_seconds=60) is None
    assert await repo.get_user_id("", ttl_seconds=60) is None


async def test_delete_closes_only_that_session_and_is_idempotent():
    repo, _ = _repo()
    user_id = uuid4()
    a = await repo.create(user_id, ttl_seconds=60)
    b = await repo.create(user_id, ttl_seconds=60)

    await repo.delete(a)
    await repo.delete(a)
    await repo.delete("")

    assert await repo.get_user_id(a, ttl_seconds=60) is None
    assert await repo.get_user_id(b, ttl_seconds=60) == user_id


async def test_delete_all_for_user_closes_every_session_of_that_user_only():
    repo, _ = _repo()
    victim, other = uuid4(), uuid4()
    t1 = await repo.create(victim, ttl_seconds=60)
    t2 = await repo.create(victim, ttl_seconds=60)
    keep = await repo.create(other, ttl_seconds=60)

    await repo.delete_all_for_user(victim)

    assert await repo.get_user_id(t1, ttl_seconds=60) is None
    assert await repo.get_user_id(t2, ttl_seconds=60) is None
    assert await repo.get_user_id(keep, ttl_seconds=60) == other
