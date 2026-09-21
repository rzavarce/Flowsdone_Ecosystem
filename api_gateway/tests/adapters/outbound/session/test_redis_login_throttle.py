"""Tests for RedisLoginThrottle."""

from __future__ import annotations

import pytest

from app.adapters.outbound.session.redis_login_throttle import RedisLoginThrottle
from api_gateway.tests.support.fakes import FakeRedisClient

pytestmark = pytest.mark.anyio


async def test_counts_failures_per_key():
    throttle = RedisLoginThrottle(FakeRedisClient())

    assert await throttle.failures("email:a") == 0
    assert await throttle.record_failure("email:a", window_seconds=900) == 1
    assert await throttle.record_failure("email:a", window_seconds=900) == 2
    assert await throttle.record_failure("email:b", window_seconds=900) == 1
    assert await throttle.failures("email:a") == 2


async def test_window_starts_at_the_first_failure_and_is_not_extended():
    client = FakeRedisClient()
    throttle = RedisLoginThrottle(client)

    await throttle.record_failure("k", window_seconds=900)
    assert client.ttls["auth:throttle:k"] == 900

    client.ttls["auth:throttle:k"] = 100  # ya corrió parte de la ventana
    await throttle.record_failure("k", window_seconds=900)
    assert client.ttls["auth:throttle:k"] == 100


async def test_reset_clears_the_bucket():
    throttle = RedisLoginThrottle(FakeRedisClient())
    await throttle.record_failure("k", window_seconds=900)

    await throttle.reset("k")

    assert await throttle.failures("k") == 0
