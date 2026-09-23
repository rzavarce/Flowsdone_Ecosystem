"""Tests for RedisQuotaCounter (Redis faked)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.adapters.outbound.billing.redis_quota_counter import RedisQuotaCounter
from api_gateway.tests.support.fakes import FakeRedisClient

pytestmark = pytest.mark.anyio


async def test_counters_are_none_until_seeded_then_keep_existing_values():
    redis = FakeRedisClient()
    counter = RedisQuotaCounter(redis)
    tenant = uuid4()

    assert await counter.get_all(tenant, "2026-09") is None
    await counter.seed(tenant, "2026-09", {})
    assert await counter.get_all(tenant, "2026-09") == {}  # initialized, all zero

    await counter.increment(tenant, "2026-09", "telegram")
    await counter.seed(tenant, "2026-09", {"telegram": 50, "voice": 2})  # never overwrites

    assert await counter.get_all(tenant, "2026-09") == {"telegram": 1, "voice": 2}
    key = f"billing:quota:{tenant}:2026-09"
    assert redis.ttls[key] == 40 * 24 * 3600


async def test_increment_returns_the_new_value_per_channel_and_period():
    counter = RedisQuotaCounter(FakeRedisClient())
    tenant = uuid4()

    assert await counter.increment(tenant, "2026-09", "telegram") == 1
    assert await counter.increment(tenant, "2026-09", "telegram", by=2) == 3
    assert await counter.increment(tenant, "2026-10", "telegram") == 1


async def test_first_time_is_true_only_once():
    counter = RedisQuotaCounter(FakeRedisClient())

    assert await counter.first_time("t:2026-09:telegram:80") is True
    assert await counter.first_time("t:2026-09:telegram:80") is False
