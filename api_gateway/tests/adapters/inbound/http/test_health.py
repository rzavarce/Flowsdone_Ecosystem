"""Tests for /health (liveness) and /ready (Postgres + Redis readiness)."""

from __future__ import annotations

import asyncio

import pytest

from app.adapters.inbound.http import health as module
from app.adapters.inbound.http.health import router
from api_gateway.tests.support.asgi import client_for_router

pytestmark = pytest.mark.anyio


class FakeConnection:
    def __init__(self, fail):
        self.fail = fail

    async def __aenter__(self):
        if self.fail:
            raise ConnectionError("db down: host=10.0.0.5 password=secret")
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement):
        return None


class FakeEngine:
    def __init__(self, fail=False):
        self.fail = fail

    def connect(self):
        return FakeConnection(self.fail)


class FakeRedis:
    def __init__(self, fail=False, hang=False):
        self.fail, self.hang = fail, hang

    async def ping(self):
        if self.hang:
            await asyncio.sleep(10)
        if self.fail:
            raise ConnectionError("redis down")
        return True


async def test_health_is_ok_without_touching_dependencies():
    async with client_for_router(router) as client:
        response = await client.get("/health")

    assert response.status_code == 200 and response.json() == {"status": "ok"}


async def test_ready_when_database_and_redis_answer():
    async with client_for_router(router, db_engine=FakeEngine(), redis_client=FakeRedis()) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_not_ready_when_a_dependency_fails_and_details_are_not_leaked():
    async with client_for_router(router, db_engine=FakeEngine(fail=True), redis_client=FakeRedis()) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "fail", "checks": {"database": "fail", "redis": "ok"}}
    assert "secret" not in response.text and "10.0.0.5" not in response.text


async def test_a_hanging_dependency_times_out(monkeypatch):
    monkeypatch.setattr(module, "CHECK_TIMEOUT_SECONDS", 0.05)
    async with client_for_router(router, db_engine=FakeEngine(), redis_client=FakeRedis(hang=True)) as client:
        response = await client.get("/ready")

    assert response.status_code == 503 and response.json()["checks"]["redis"] == "fail"


async def test_dependencies_the_gateway_runs_without_are_skipped():
    async with client_for_router(router) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "skipped", "redis": "skipped"}
