"""Admin API for CRM integrations and manual handoffs: roles, tenant
isolation, secrets shown only once, URL validation and the test event.
"""

from __future__ import annotations

import pytest

from api_gateway.tests.support.admin_world import CSRF, World, cookie

pytestmark = pytest.mark.anyio

BASE = "/internal/admin"


@pytest.fixture
def world():
    return World.build()


async def _call(world, role, method, path, json=None):
    token = await world.token(role)
    async with world.client() as c:
        return await c.request(method, BASE + path, headers={**cookie(token), **CSRF}, json=json)


def _create(project_id, url="https://crm.example.com/hook"):
    return {"project_id": str(project_id), "provider": "generic_webhook", "config": {"url": url}}


async def test_a_manager_creates_an_integration_and_sees_its_secrets_only_once(world):
    created = await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))

    assert created.status_code == 201
    body = created.json()
    assert body["signing_secret"] and body["api_key"]
    assert body["reply_url"].endswith(f"/integrations/crm/{body['id']}/messages")

    listed = await _call(world, "tenant_manager", "GET", "/crm-integrations")
    assert [i["id"] for i in listed.json()] == [body["id"]]
    assert "api_key" not in listed.json()[0] and "signing_secret" not in listed.json()[0]


async def test_one_integration_per_project(world):
    await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))

    again = await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))

    assert again.status_code == 409


async def test_a_url_the_gateway_may_not_call_is_refused(world):
    resp = await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id, "http://10.0.0.5/x"))

    assert resp.status_code == 400


async def test_other_tenants_projects_and_integrations_are_invisible(world):
    other = await _call(world, "admin", "POST", "/crm-integrations", _create(world.project_b.id))
    other_id = other.json()["id"]

    assert (await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_b.id))).status_code == 404
    assert (await _call(world, "tenant_manager", "GET", "/crm-integrations")).json() == []
    for method, path in (("PATCH", f"/crm-integrations/{other_id}"), ("DELETE", f"/crm-integrations/{other_id}"),
                         ("POST", f"/crm-integrations/{other_id}/rotate-secrets")):
        assert (await _call(world, "tenant_manager", method, path, {} if method == "PATCH" else None)).status_code == 404


async def test_a_botmaster_can_read_but_not_change_integrations(world):
    assert (await _call(world, "botmaster", "GET", "/crm-integrations")).status_code == 200
    assert (await _call(world, "botmaster", "POST", "/crm-integrations", _create(world.project_a.id))).status_code == 403


async def test_update_rotate_test_and_delete(world):
    created = (await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))).json()
    iid = created["id"]

    updated = await _call(world, "tenant_manager", "PATCH", f"/crm-integrations/{iid}", {"status": "inactive", "config": {"url": "https://crm.example.com/v2"}})
    assert (updated.json()["status"], updated.json()["config"]["url"]) == ("inactive", "https://crm.example.com/v2")

    rotated = await _call(world, "tenant_manager", "POST", f"/crm-integrations/{iid}/rotate-secrets")
    assert rotated.status_code == 200 and rotated.json()["api_key"]

    tested = await _call(world, "tenant_manager", "POST", f"/crm-integrations/{iid}/test")
    assert tested.json() == {"ok": True, "error": None}
    assert world.crm_provider.delivered[0].type == "integration.test"

    world.crm_provider.error = ValueError("the CRM rejected the event (401)")
    failed = await _call(world, "tenant_manager", "POST", f"/crm-integrations/{iid}/test")
    assert failed.json() == {"ok": False, "error": "the CRM rejected the event (401)"}

    assert (await _call(world, "tenant_manager", "DELETE", f"/crm-integrations/{iid}")).status_code == 204
    assert (await _call(world, "tenant_manager", "GET", "/crm-integrations")).json() == []


async def test_handing_a_conversation_over_by_hand(world):
    world.crm_state()
    no_integration = await _call(world, "tenant_manager", "POST", "/crm-handoffs", {"conversation_id": world.live_session_a.id})
    assert no_integration.status_code == 409

    await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))
    handed = await _call(world, "tenant_manager", "POST", "/crm-handoffs", {"conversation_id": world.live_session_a.id, "reason": "VIP"})
    assert handed.status_code == 201 and handed.json()["status"] == "open"

    foreign = await _call(world, "tenant_manager", "POST", "/crm-handoffs", {"conversation_id": world.live_session_b.id})
    missing = await _call(world, "tenant_manager", "POST", "/crm-handoffs", {"conversation_id": "gone"})
    assert (foreign.status_code, missing.status_code) == (404, 404)


async def test_langflow_can_hand_over_with_the_conversation_uuid_it_knows(world):
    world.crm_state()
    world.conversations.conversations[world.conversation_a.id] = world.conversation_a.model_copy(
        update={"session_id": world.live_session_a.id}
    )
    await _call(world, "tenant_manager", "POST", "/crm-integrations", _create(world.project_a.id))

    handed = await _call(world, "tenant_manager", "POST", "/crm-handoffs", {"conversation_id": str(world.conversation_a.id)})

    assert handed.status_code == 201 and handed.json()["conversation_id"] == world.live_session_a.id
