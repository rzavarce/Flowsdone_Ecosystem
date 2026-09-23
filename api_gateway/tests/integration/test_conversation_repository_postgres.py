"""Integration tests for SqlAlchemyConversationRepository against a
real Postgres with the Alembic schema applied.

Skipped unless TEST_POSTGRES_URL points at a throwaway database
(postgresql+asyncpg://...) already migrated to head - never the real
gatewaydb: every test writes rows.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.infrastructure.database import create_sessionmaker
from api_gateway.tests.support.fakes import make_conversation

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)
WEEK = timedelta(days=7)


@pytest.fixture
async def repo_and_project():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    tenant_id, project_id = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, status) VALUES (:id, 'it', :slug, 'active')"),
            {"id": tenant_id, "slug": f"it-{tenant_id}"},
        )
        await conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, slug, status) VALUES (:id, :tenant_id, 'it', :slug, 'active')"),
            {"id": project_id, "tenant_id": tenant_id, "slug": f"it-{project_id}"},
        )
    yield SqlAlchemyConversationRepository(create_sessionmaker(engine)), tenant_id, project_id
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await engine.dispose()


def _conversation(tenant_id, project_id, **overrides):
    return make_conversation(tenant_id=tenant_id, project_id=project_id, **overrides)


async def test_open_get_and_record_messages(repo_and_project):
    repo, tenant_id, project_id = repo_and_project
    conversation = await repo.open(_conversation(tenant_id, project_id, started_at=T0, last_inbound_at=T0, last_message_at=T0))

    await repo.record_message(conversation.id, direction="inbound", at=T0 + timedelta(hours=1))
    await repo.record_message(conversation.id, direction="outbound", at=T0 + timedelta(hours=2))
    # Out of order: must not move timestamps backwards.
    await repo.record_message(conversation.id, direction="inbound", at=T0 + timedelta(minutes=30))

    stored = await repo.get(conversation.id)
    assert stored.status == "open"
    assert stored.inbound_count == 2
    assert stored.outbound_count == 1
    assert stored.last_inbound_at == T0 + timedelta(hours=1)
    assert stored.last_message_at == T0 + timedelta(hours=2)


async def test_only_one_open_conversation_per_session(repo_and_project):
    repo, tenant_id, project_id = repo_and_project
    first = await repo.open(_conversation(tenant_id, project_id, session_id="s-1"))

    second = await repo.open(_conversation(tenant_id, project_id, session_id="s-1"))

    assert second.id == first.id

    assert await repo.close(first.id, reason="manual", closed_at=T0) is True
    assert await repo.close(first.id, reason="manual", closed_at=T0) is False
    third = await repo.open(_conversation(tenant_id, project_id, session_id="s-1"))
    assert third.id != first.id


async def test_close_expired_stamps_the_real_expiry_and_reason(repo_and_project):
    repo, tenant_id, project_id = repo_and_project
    now = T0 + timedelta(days=10)
    idle = await repo.open(
        _conversation(tenant_id, project_id, started_at=now - 2 * DAY, last_inbound_at=now - timedelta(hours=30))
    )
    too_long = await repo.open(
        _conversation(tenant_id, project_id, started_at=now - 8 * DAY, last_inbound_at=now - timedelta(hours=1))
    )
    active = await repo.open(
        _conversation(tenant_id, project_id, started_at=now - DAY, last_inbound_at=now - timedelta(hours=1))
    )

    closed = await repo.close_expired(now=now, inactivity=DAY, max_duration=WEEK, limit=100)

    by_id = {c.id: c for c in closed}
    assert idle.id in by_id and too_long.id in by_id and active.id not in by_id
    assert by_id[idle.id].close_reason == "inactivity"
    assert by_id[idle.id].closed_at == now - timedelta(hours=6)
    assert by_id[too_long.id].close_reason == "max_duration"
    assert by_id[too_long.id].closed_at == now - DAY
    assert (await repo.get(active.id)).status == "open"
