"""Integration tests for contact cards against a real, migrated, throwaway
Postgres (TEST_POSTGRES_URL): the upsert rules and searching conversations
by the name on their contact's card."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from app.adapters.outbound.db.conversation_contact_repository import SqlAlchemyContactRepository
from app.adapters.outbound.db.conversation_repository import SqlAlchemyConversationRepository
from app.infrastructure.database import create_sessionmaker
from api_gateway.tests.support.fakes import make_conversation

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL not set"),
]


@pytest.fixture
async def ctx():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    tenant_id, project_id = uuid.uuid4(), uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, name, slug, status) VALUES (:id, 'it', :slug, 'active')"),
            {"id": tenant_id, "slug": f"it-{tenant_id}"},
        )
        await conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, slug, status) VALUES (:id, :t, 'it', :slug, 'active')"),
            {"id": project_id, "t": tenant_id, "slug": f"it-{project_id}"},
        )
    yield dict(sessionmaker=create_sessionmaker(engine), tenant_id=tenant_id, project_id=project_id)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
    await engine.dispose()


async def test_upsert_creates_updates_and_only_fills_empty_fields_when_asked(ctx):
    repo = SqlAlchemyContactRepository(ctx["sessionmaker"])
    key = (ctx["tenant_id"], "voice", "+34600111222")

    created = await repo.upsert(key, {"name": "Ana Pérez"})
    captured = await repo.upsert(key, {"name": "Ana Peres", "email": "ana@example.com"}, only_empty=True)
    edited = await repo.upsert(key, {"name": "Ana P.", "email": None})

    assert created.name == "Ana Pérez" and created.email is None
    assert captured.id == created.id
    assert captured.name == "Ana Pérez" and captured.email == "ana@example.com"
    assert edited.name == "Ana P." and edited.email is None
    assert (await repo.get(key)).name == "Ana P."


async def test_find_many_returns_only_the_existing_ones(ctx):
    repo = SqlAlchemyContactRepository(ctx["sessionmaker"])
    ana = (ctx["tenant_id"], "voice", "+34600111222")
    luis = (ctx["tenant_id"], "telegram", "@luis")
    await repo.upsert(ana, {"name": "Ana"})
    await repo.upsert(luis, {"name": "Luis"})

    found = await repo.find_many([ana, luis, (ctx["tenant_id"], "voice", "+34000000000"), (uuid.uuid4(), "voice", "+34600111222")])

    assert {k: c.name for k, c in found.items()} == {ana: "Ana", luis: "Luis"}
    assert await repo.find_many([]) == {}


async def test_conversations_can_be_searched_by_the_name_on_their_card(ctx):
    contacts = SqlAlchemyContactRepository(ctx["sessionmaker"])
    conversations = SqlAlchemyConversationRepository(ctx["sessionmaker"])
    named = make_conversation(tenant_id=ctx["tenant_id"], project_id=ctx["project_id"], channel_type="voice",
                              contact="client:demo-abc", session_id=f"s-{uuid.uuid4()}")
    unnamed = make_conversation(tenant_id=ctx["tenant_id"], project_id=ctx["project_id"], channel_type="voice",
                                contact="+34600999999", session_id=f"s-{uuid.uuid4()}")
    await conversations.open(named)
    await conversations.open(unnamed)
    await contacts.upsert((ctx["tenant_id"], "voice", "client:demo-abc"), {"name": "Ana Pérez"})

    by_name = await conversations.list(tenant_ids=[ctx["tenant_id"]], contact="pérez")
    by_identifier = await conversations.list(tenant_ids=[ctx["tenant_id"]], contact="999")
    nobody = await conversations.list(tenant_ids=[ctx["tenant_id"]], contact="luis")

    assert [c.id for c in by_name] == [named.id]
    assert [c.id for c in by_identifier] == [unnamed.id]
    assert nobody == []
