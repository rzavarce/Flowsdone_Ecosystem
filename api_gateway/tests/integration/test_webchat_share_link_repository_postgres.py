"""Integration tests for SqlAlchemyWebchatShareLinkRepository against a real,
migrated, throwaway Postgres (TEST_POSTGRES_URL)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.webchat_share_link_repository import SqlAlchemyWebchatShareLinkRepository
from app.infrastructure.database import create_sessionmaker

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture
async def ctx():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    tenant_id, project_id, agent_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, status) VALUES (:id, 'it', :slug, 'active')"),
            {"id": tenant_id, "slug": f"it-{tenant_id}"},
        )
        await conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, slug, status) VALUES (:id, :t, 'it', :slug, 'active')"),
            {"id": project_id, "t": tenant_id, "slug": f"it-{project_id}"},
        )
        for aid, name in ((agent_id, "A"), (other_id, "B")):
            await conn.execute(
                text(
                    "INSERT INTO agents (id, project_id, name, langflow_flow_id, config, is_default, status) "
                    "VALUES (:id, :p, :n, 'flow', '{}', false, 'active')"
                ),
                {"id": aid, "p": project_id, "n": name},
            )
    yield dict(engine=engine, sessionmaker=create_sessionmaker(engine), agent_id=agent_id, other_id=other_id)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await engine.dispose()


async def test_links_roundtrip_with_the_token_encrypted(ctx):
    repo = SqlAlchemyWebchatShareLinkRepository(ctx["sessionmaker"])
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    by = uuid.uuid4()

    link = await repo.create(agent_id=ctx["agent_id"], token="tok-secret-1", token_hash="h1", created_by=by, expires_at=expires)

    found = await repo.get_by_token_hash("h1")
    assert found.id == link.id and found.token.get_secret_value() == "tok-secret-1"
    assert found.created_by == by and found.expires_at == expires and found.revoked_at is None
    assert await repo.get_by_token_hash("nope") is None
    async with ctx["engine"].connect() as conn:
        raw = (
            await conn.execute(text("SELECT credentials::text FROM webchat_share_links WHERE id = :id"), {"id": link.id})
        ).scalar_one()
    assert "tok-secret-1" not in raw


async def test_list_is_per_agent_newest_first_and_hides_revoked(ctx):
    repo = SqlAlchemyWebchatShareLinkRepository(ctx["sessionmaker"])
    first = await repo.create(agent_id=ctx["agent_id"], token="t1", token_hash="l1", created_by=None, expires_at=None)
    second = await repo.create(agent_id=ctx["agent_id"], token="t2", token_hash="l2", created_by=None, expires_at=None)
    await repo.create(agent_id=ctx["other_id"], token="t3", token_hash="l3", created_by=None, expires_at=None)

    assert [l.id for l in await repo.list_by_agent(ctx["agent_id"])] == [second.id, first.id]

    now = datetime.now(timezone.utc)
    assert await repo.revoke(ctx["other_id"], first.id, now) is False  # not that agent's link
    assert await repo.revoke(ctx["agent_id"], first.id, now) is True
    assert await repo.revoke(ctx["agent_id"], first.id, now) is False  # already revoked

    assert [l.id for l in await repo.list_by_agent(ctx["agent_id"])] == [second.id]
    assert (await repo.get_by_token_hash("l1")).revoked_at is not None


async def test_deleting_the_agent_deletes_its_links(ctx):
    repo = SqlAlchemyWebchatShareLinkRepository(ctx["sessionmaker"])
    await repo.create(agent_id=ctx["other_id"], token="t9", token_hash="d9", created_by=None, expires_at=None)

    async with ctx["engine"].begin() as conn:
        await conn.execute(text("DELETE FROM agents WHERE id = :id"), {"id": ctx["other_id"]})

    assert await repo.get_by_token_hash("d9") is None
