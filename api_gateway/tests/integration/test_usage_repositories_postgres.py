"""Integration tests for the cost catalog and sync cursor repositories
against a real, migrated, throwaway Postgres (TEST_POSTGRES_URL)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.adapters.outbound.db.usage_repositories import (
    SqlAlchemyCostRateRepository,
    SqlAlchemySyncCursorRepository,
)
from app.infrastructure.database import create_sessionmaker
from api_gateway.tests.support.fakes import make_cost_rate

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture
async def sessionmaker():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    yield create_sessionmaker(engine)
    await engine.dispose()


async def test_cost_rates_create_list_delete(sessionmaker):
    repo = SqlAlchemyCostRateRepository(sessionmaker)
    rate = make_cost_rate(sku=f"it-{uuid4()}*", note="precio de lista")

    stored = await repo.create(rate)

    assert stored.created_at is not None
    assert rate.id in {r.id for r in await repo.list_all()}
    assert await repo.delete(rate.id) is True
    assert await repo.delete(rate.id) is False


async def test_sync_cursor_upsert(sessionmaker):
    repo = SqlAlchemySyncCursorRepository(sessionmaker)
    name = f"it-{uuid4()}"
    first = datetime(2026, 9, 1, tzinfo=timezone.utc)
    second = datetime(2026, 9, 2, tzinfo=timezone.utc)

    assert await repo.get(name) is None
    await repo.set(name, first)
    await repo.set(name, second)

    assert await repo.get(name) == second
