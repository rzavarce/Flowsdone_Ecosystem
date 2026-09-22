"""Tests for RedisSsoTicketStore."""

from __future__ import annotations

import pytest

from app.adapters.outbound.session.redis_sso_ticket_store import RedisSsoTicketStore
from api_gateway.tests.support.fakes import FakeRedisClient

pytestmark = pytest.mark.anyio


def _store():
    client = FakeRedisClient()
    return RedisSsoTicketStore(client), client


async def test_a_ticket_returns_its_payload_once():
    store, _ = _store()
    ticket = await store.issue({"tenant_id": "t1", "path": "/all"}, ttl_seconds=30)

    assert await store.redeem(ticket) == {"tenant_id": "t1", "path": "/all"}
    assert await store.redeem(ticket) is None


async def test_tickets_are_unguessable_and_unique():
    store, _ = _store()
    a = await store.issue({}, ttl_seconds=30)
    b = await store.issue({}, ttl_seconds=30)
    assert a != b and len(a) >= 40


async def test_only_a_hash_is_stored_and_it_expires():
    store, client = _store()
    ticket = await store.issue({"tenant_id": "t1"}, ttl_seconds=30)

    assert all(ticket not in key for key in client.store)
    assert list(client.ttls.values()) == [30]


async def test_unknown_and_empty_tickets_are_rejected():
    store, _ = _store()
    assert await store.redeem("nope") is None
    assert await store.redeem("") is None
