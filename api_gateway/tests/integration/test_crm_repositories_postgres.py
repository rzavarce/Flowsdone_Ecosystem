"""Integration tests for the CRM repositories against a real Postgres
with the Alembic schema applied (skipped unless TEST_POSTGRES_URL is set).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.crm_repositories import SqlAlchemyCrmIntegrationRepository, SqlAlchemyHandoffRepository
from app.domain.models.crm import Handoff
from app.domain.ports.outbound import AlreadyExistsError
from app.infrastructure.database import create_sessionmaker

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]

T0 = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
async def repos():
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
    sessionmaker = create_sessionmaker(engine)
    yield SqlAlchemyCrmIntegrationRepository(sessionmaker), SqlAlchemyHandoffRepository(sessionmaker), tenant_id, project_id
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await engine.dispose()


async def test_integration_crud_with_encrypted_credentials_and_one_per_project(repos):
    integrations, _, tenant_id, project_id = repos
    created = await integrations.create(
        tenant_id=tenant_id, project_id=project_id, provider="generic_webhook",
        config={"url": "https://crm.example.com/h"}, credentials={"signing_secret": "S", "api_key": "K"},
    )

    assert (await integrations.get_for_project(project_id)).credentials == {"signing_secret": "S", "api_key": "K"}
    with pytest.raises(AlreadyExistsError):
        await integrations.create(tenant_id=tenant_id, project_id=project_id, provider="generic_webhook", config={}, credentials={})

    updated = await integrations.update(created.id, status="inactive", config={"url": "https://crm.example.com/v2"})
    assert (updated.status, updated.config["url"], updated.credentials["api_key"]) == ("inactive", "https://crm.example.com/v2", "K")
    assert [i.id for i in await integrations.list(tenant_ids=[tenant_id])] == [created.id]
    assert await integrations.delete(created.id) is True
    assert await integrations.get(created.id) is None


async def test_one_open_handoff_per_conversation_and_closing_is_atomic(repos):
    _, handoffs, tenant_id, project_id = repos
    session_id = f"{project_id}:whatsapp_360dialog:34699000111"

    def _new():
        return Handoff(
            id=uuid.uuid4(), session_id=session_id, tenant_id=tenant_id, project_id=project_id,
            integration_id=uuid.uuid4(), provider="generic_webhook", channel_type="whatsapp_360dialog",
            contact="34699000111", opened_at=T0,
        )

    first = await handoffs.open(_new())
    second = await handoffs.open(_new())
    assert second.id == first.id

    closed = await handoffs.close(first.id, status="closed", reason="agent", at=T0 + timedelta(minutes=5))
    assert (closed.status, closed.close_reason) == ("closed", "agent")
    assert await handoffs.close(first.id, status="expired", reason="expired", at=T0) is None
    assert await handoffs.get_open(session_id) is None

    reopened = await handoffs.open(_new())
    assert reopened.id != first.id and (await handoffs.get_open(session_id)).id == reopened.id
