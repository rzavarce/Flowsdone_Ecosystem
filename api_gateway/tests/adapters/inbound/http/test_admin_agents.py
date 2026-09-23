"""HTTP tests for agent registration: flow verification for console users,
machine callers, default agent, deletion with channels, and the project
flows listing."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import settings
from api_gateway.tests.support.admin_world import CSRF, World, cookie

pytestmark = pytest.mark.anyio

BASE = "/internal/admin"


@pytest.fixture
def world():
    return World.build()


async def _call(client, method, path, *, token=None, api_key=None, json=None):
    headers = {**CSRF}
    if token:
        headers.update(cookie(token))
    if api_key:
        headers["X-Admin-Api-Key"] = api_key
    return await client.request(method, BASE + path, headers=headers, json=json)


async def test_lists_the_project_flows_with_their_agent(world):
    token = await world.token("botmaster")
    async with world.client() as c:
        own = await _call(c, "GET", f"/langflow/flows?project_id={world.project_a.id}", token=token)
        other = await _call(c, "GET", f"/langflow/flows?project_id={world.project_b.id}", token=token)
        client = await _call(c, "GET", f"/langflow/flows?project_id={world.project_a.id}", token=await world.token("client"))

    assert own.status_code == 200
    flows = {f["id"]: f["agent_id"] for f in own.json()}
    assert flows == {"f": None, "fa": str(world.agent_a.id), "f2": None}
    assert other.status_code == 404 and client.status_code == 403


async def test_console_users_can_only_register_flows_of_the_project_folder(world):
    token = await world.token("botmaster")
    async with world.client() as c:
        ok = await _call(c, "POST", "/agents", token=token,
                         json={"project_id": str(world.project_a.id), "name": "Citas", "langflow_flow_id": "f2"})
        foreign = await _call(c, "POST", "/agents", token=token,
                              json={"project_id": str(world.project_a.id), "name": "Otro", "langflow_flow_id": "fb"})
        machine = await _call(c, "POST", "/agents", api_key=settings.ADMIN_API_KEY,
                              json={"project_id": str(world.project_a.id), "name": "Legacy", "langflow_flow_id": "anywhere"})

    assert ok.status_code == 201
    assert foreign.status_code == 400 and "Langflow folder" in foreign.json()["detail"]
    assert machine.status_code == 201


async def test_changing_the_flow_is_verified_and_default_is_exclusive(world):
    token = await world.token("tenant_manager")
    async with world.client() as c:
        created = await _call(c, "POST", "/agents", token=token, json={
            "project_id": str(world.project_a.id), "name": "Nuevo", "langflow_flow_id": "f2", "is_default": True,
        })
        bad_flow = await _call(c, "PATCH", f"/agents/{created.json()['id']}", token=token, json={"langflow_flow_id": "fb"})
        suspended = await _call(c, "PATCH", f"/agents/{created.json()['id']}", token=token, json={"status": "suspended"})

    assert created.json()["is_default"] is True
    assert world.agents.items[world.agent_a.id].is_default is False
    assert bad_flow.status_code == 400
    assert suspended.json()["status"] == "suspended"


async def test_an_agent_with_channels_cannot_be_deleted(world):
    token = await world.token("admin")
    async with world.client() as c:
        in_use = await _call(c, "DELETE", f"/agents/{world.agent_a.id}", token=token)
        free = await _call(c, "POST", "/agents", token=token,
                           json={"project_id": str(world.project_a.id), "name": "Libre", "langflow_flow_id": "f"})
        deleted = await _call(c, "DELETE", f"/agents/{free.json()['id']}", token=token)
        missing = await _call(c, "DELETE", f"/agents/{uuid4()}", token=token)

    assert in_use.status_code == 409 and in_use.json()["detail"] == "agent has channels"
    assert deleted.status_code == 204 and missing.status_code == 404


async def test_base_agent_is_created_as_default_in_own_projects_only(world):
    token = await world.token("botmaster")
    async with world.client() as c:
        created = await _call(c, "POST", "/agents/base", token=token, json={
            "project_id": str(world.project_a.id), "assistant_name": " Fibi ", "tone": "formal", "instructions": "Fibra.",
        })
        other = await _call(c, "POST", "/agents/base", token=token, json={
            "project_id": str(world.project_b.id), "assistant_name": "X",
        })
        bad_tone = await _call(c, "POST", "/agents/base", token=token, json={
            "project_id": str(world.project_a.id), "assistant_name": "X", "tone": "gracioso",
        })

    assert created.status_code == 201
    assert created.json()["name"] == "Fibi" and created.json()["is_default"] is True
    assert world.base_agent.calls[-1]["tone"] == "formal"
    assert world.agents.items[world.agent_a.id].is_default is False
    assert other.status_code == 404 and bad_tone.status_code == 422


@pytest.mark.parametrize("role,expected", [("admin", 200), ("tenant_manager", 200), ("botmaster", 403), ("client", 403)])
async def test_onboarding_status_roles(world, role, expected):
    async with world.client() as c:
        resp = await _call(c, "GET", f"/tenants/{world.tenant_a.id}/onboarding", token=await world.token(role))
    assert resp.status_code == expected
    if expected == 200:
        assert resp.json()["next_step"] == "plan" and resp.json()["checks"][0] == {"key": "billing", "status": "ok", "detail": "Acme"}


async def test_onboarding_status_of_another_or_unknown_tenant_is_404(world):
    async with world.client() as c:
        other = await _call(c, "GET", f"/tenants/{world.tenant_b.id}/onboarding", token=await world.token("tenant_manager"))
        unknown = await _call(c, "GET", f"/tenants/{uuid4()}/onboarding", token=await world.token("admin"))
    assert other.status_code == unknown.status_code == 404
