"""End-to-end (ASGI, fakes) tests for the admin contact list endpoints."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.use_cases.conversation_contacts import contact_key
from api_gateway.tests.support.admin_world import CSRF, World, cookie
from api_gateway.tests.support.fakes import make_conversation

pytestmark = pytest.mark.anyio

BASE = "/internal/admin"


@pytest.fixture
def world():
    return World.build()


async def _call(client, method, path, *, token, json=None):
    return await client.request(method, BASE + path, headers={**cookie(token), **CSRF}, json=json)


async def _card(world, conversation, **fields):
    return await world.contacts.upsert(contact_key(conversation), fields)


async def test_contacts_are_listed_only_for_the_callers_tenants_and_can_be_searched(world):
    ana = await _card(world, world.conversation_a, name="Ana Pérez", email="ana@example.com")
    await _card(world, world.conversation_b, name="Luis")

    async with world.client() as c:
        mine = await _call(c, "GET", "/contacts", token=await world.token("botmaster"))
        everything = await _call(c, "GET", "/contacts", token=await world.token("admin"))
        by_email = await _call(c, "GET", "/contacts?q=ANA@EXAMPLE", token=await world.token("admin"))
        nobody = await _call(c, "GET", "/contacts?q=zzz", token=await world.token("admin"))
        client_role = await _call(c, "GET", "/contacts", token=await world.token("client"))

    assert [x["id"] for x in mine.json()] == [str(ana.id)]
    assert {x["name"] for x in everything.json()} == {"Ana Pérez", "Luis"}
    assert [x["name"] for x in by_email.json()] == ["Ana Pérez"]
    assert nobody.json() == []
    assert client_role.status_code == 403


async def test_a_contact_shows_only_their_latest_conversations(world):
    ana = await _card(world, world.conversation_a, name="Ana")
    for _ in range(7):
        extra = make_conversation(
            tenant_id=world.conversation_a.tenant_id, project_id=world.conversation_a.project_id,
            channel_type=world.conversation_a.channel_type, contact=world.conversation_a.contact,
        )
        world.conversations.conversations[extra.id] = extra
    someone_else = make_conversation(
        tenant_id=world.conversation_a.tenant_id, project_id=world.conversation_a.project_id,
        channel_type=world.conversation_a.channel_type, contact="+34 699 999",
    )
    world.conversations.conversations[someone_else.id] = someone_else

    async with world.client() as c:
        detail = await _call(c, "GET", f"/contacts/{ana.id}", token=await world.token("botmaster"))

    body = detail.json()
    assert detail.status_code == 200 and body["contact"]["name"] == "Ana"
    assert len(body["conversations"]) == 5
    assert all(x["contact"] == world.conversation_a.contact for x in body["conversations"])
    assert all(x["contact_name"] == "Ana" for x in body["conversations"])


async def test_staff_edit_a_contact_from_the_list(world):
    ana = await _card(world, world.conversation_a, name="Ana", phone="600111222")

    async with world.client() as c:
        edited = await _call(c, "PATCH", f"/contacts/{ana.id}", token=await world.token("botmaster"),
                             json={"name": "Ana Pérez", "phone": "", "username": "@ana"})
        bad = await _call(c, "PATCH", f"/contacts/{ana.id}", token=await world.token("botmaster"),
                          json={"email": "no-es-un-email"})

    assert edited.status_code == 200
    assert (edited.json()["name"], edited.json()["phone"], edited.json()["username"]) == ("Ana Pérez", None, "@ana")
    assert bad.status_code == 422


async def test_a_contact_of_another_tenant_or_unknown_is_not_found(world):
    luis = await _card(world, world.conversation_b, name="Luis")

    async with world.client() as c:
        token = await world.token("botmaster")
        foreign = await _call(c, "GET", f"/contacts/{luis.id}", token=token)
        foreign_edit = await _call(c, "PATCH", f"/contacts/{luis.id}", token=token, json={"name": "X"})
        missing = await _call(c, "GET", f"/contacts/{uuid4()}", token=token)

    assert foreign.status_code == foreign_edit.status_code == missing.status_code == 404
    assert world.contacts.contacts[contact_key(world.conversation_b)].name == "Luis"
