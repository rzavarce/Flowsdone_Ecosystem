"""HTTP tests for the embedded-Langflow SSO: who may open it, and what the
public endpoint sets on the browser."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.adapters.inbound.http.langflow_sso import router as sso_router
from app.application.use_cases.langflow_sso import LangflowLanding, LangflowTargetNotFoundError
from app.core.config import settings
from app.domain.ports.outbound import LangflowSessionError, LangflowTokens
from api_gateway.tests.support.admin_world import CSRF, World, cookie
from api_gateway.tests.support.asgi import client_for_router

pytestmark = pytest.mark.anyio

URL = "/internal/admin/langflow/session"


class FakePrepare:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list = []
        self.error = error

    async def execute(self, tenant_id, project_id=None):
        self.calls.append((tenant_id, project_id))
        if self.error:
            raise self.error
        return "tk 1/+"


def _client(world: World, prepare: FakePrepare):
    return client_for_router(
        __import__("app.adapters.inbound.http.admin", fromlist=["router"]).router,
        **world.state(),
        prepare_langflow_session_use_case=prepare,
    )


async def test_admin_gets_a_sso_url_with_an_encoded_ticket(monkeypatch):
    monkeypatch.setattr(settings, "LANGFLOW_SSO_BASE_URL", "https://agents.example.com")
    world, prepare = World.build(), FakePrepare()
    async with _client(world, prepare) as client:
        response = await client.post(
            URL, json={"tenant_id": str(world.tenant_b.id)}, headers={**cookie(await world.token("admin")), **CSRF}
        )

    assert response.status_code == 200
    assert response.json() == {"url": "https://agents.example.com/langflow-sso?ticket=tk%201/%2B"}
    assert prepare.calls == [(world.tenant_b.id, None)]


@pytest.mark.parametrize("role", ["tenant_manager", "botmaster"])
async def test_any_staff_role_may_open_langflow(role):
    # Aceptado a sabiendas: tenant_manager/botmaster son personal de Flowsdone,
    # no de clientes (ver POLICY["langflow"] en access_control.py).
    world, prepare = World.build(), FakePrepare()
    async with _client(world, prepare) as client:
        response = await client.post(
            URL, json={"tenant_id": str(world.tenant_a.id)}, headers={**cookie(await world.token(role)), **CSRF}
        )

    assert response.status_code == 200
    assert prepare.calls == [(world.tenant_a.id, None)]


async def test_client_role_may_not_open_langflow():
    world, prepare = World.build(), FakePrepare()
    async with _client(world, prepare) as client:
        response = await client.post(
            URL, json={"tenant_id": str(world.tenant_a.id)}, headers={**cookie(await world.token("client")), **CSRF}
        )

    assert response.status_code == 403
    assert prepare.calls == []


async def test_it_requires_a_session_and_the_csrf_header():
    world, prepare = World.build(), FakePrepare()
    body = {"tenant_id": str(world.tenant_a.id)}
    async with _client(world, prepare) as client:
        assert (await client.post(URL, json=body)).status_code == 401
        no_csrf = await client.post(URL, json=body, headers=cookie(await world.token("admin")))
    assert no_csrf.status_code == 403
    assert prepare.calls == []


async def test_a_project_of_another_tenant_or_a_missing_one_is_404():
    world, prepare = World.build(), FakePrepare(error=LangflowTargetNotFoundError("tenant not found"))
    headers = {**cookie(await world.token("admin")), **CSRF}
    async with _client(world, prepare) as client:
        missing_project = await client.post(
            URL, json={"tenant_id": str(world.tenant_a.id), "project_id": str(uuid4())}, headers=headers
        )
        missing_tenant = await client.post(URL, json={"tenant_id": str(uuid4())}, headers=headers)

    assert missing_project.status_code == 404
    assert missing_tenant.status_code == 404  # the use case reports it


async def test_a_langflow_failure_is_a_502():
    world, prepare = World.build(), FakePrepare(error=LangflowSessionError("login refused"))
    async with _client(world, prepare) as client:
        response = await client.post(
            URL, json={"tenant_id": str(world.tenant_a.id)}, headers={**cookie(await world.token("admin")), **CSRF}
        )
    assert response.status_code == 502


class FakeRedeem:
    def __init__(self, landing=None, error=None) -> None:
        self.landing, self.error, self.tickets = landing, error, []

    async def execute(self, ticket):
        self.tickets.append(ticket)
        if self.error:
            raise self.error
        return self.landing


def _landing(path="/all/folder/f1"):
    return LangflowLanding(tokens=LangflowTokens(access_token="acc", refresh_token="ref"), path=path)


async def _get(redeem, ticket="abc"):
    async with client_for_router(sso_router, redeem_langflow_ticket_use_case=redeem) as client:
        return await client.get("/langflow-sso", params={"ticket": ticket}, follow_redirects=False)


async def test_redeeming_redirects_into_langflow_with_its_session_cookies(monkeypatch):
    monkeypatch.setattr(settings, "LANGFLOW_PUBLIC_URL", "https://agents.example.com")
    redeem = FakeRedeem(_landing())

    response = await _get(redeem)

    assert response.status_code == 303
    assert response.headers["location"] == "https://agents.example.com/all/folder/f1"
    assert response.headers["cache-control"] == "no-store"
    assert redeem.tickets == ["abc"]
    cookies = {c.split("=")[0]: c for c in response.headers.get_list("set-cookie")}
    access, refresh = cookies["access_token_lf"], cookies["refresh_token_lf"]
    assert "acc" in access and "HttpOnly" not in access  # Langflow's frontend reads it from JS
    assert "HttpOnly" in refresh
    for header in (access, refresh):
        assert "Secure" in header and "SameSite=lax" in header and "Domain" not in header


async def test_cookies_are_not_secure_on_plain_http_dev(monkeypatch):
    monkeypatch.setattr(settings, "LANGFLOW_PUBLIC_URL", "http://localhost:7860")
    response = await _get(FakeRedeem(_landing()))
    assert all("Secure" not in c for c in response.headers.get_list("set-cookie"))


async def test_an_invalid_or_used_ticket_is_a_400_page_without_cookies():
    response = await _get(FakeRedeem(None))
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers


async def test_a_langflow_failure_shows_a_502_page():
    response = await _get(FakeRedeem(error=LangflowSessionError("down")))
    assert response.status_code == 502
    assert "set-cookie" not in response.headers


async def test_an_oversized_ticket_is_rejected_before_reaching_the_use_case():
    redeem = FakeRedeem(_landing())
    response = await _get(redeem, ticket="x" * 500)
    assert response.status_code == 422 and redeem.tickets == []
