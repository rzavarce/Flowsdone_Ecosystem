"""Tests for LangflowAdminClient (Langflow answered by an httpx MockTransport)."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.outbound.langflow.admin_client import LangflowAdminClient
from app.core.config import settings
from app.domain.ports.outbound import LangflowSessionError

pytestmark = pytest.mark.anyio


def _client(handler) -> tuple[LangflowAdminClient, list]:
    seen: list = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.AsyncClient(base_url="http://langflow", transport=httpx.MockTransport(record))
    return LangflowAdminClient(http), seen


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setattr(settings, "LANGFLOW_API_KEY", "gateway-key")


async def test_ensure_user_creates_activates_and_uses_the_gateway_key():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(201, json={"id": "u1"})
        return httpx.Response(200, json={})

    client, seen = _client(handler)

    assert await client.ensure_user("tenant-a", "pw") == "u1"
    assert [(r.method, r.url.path) for r in seen] == [("POST", "/api/v1/users/"), ("PATCH", "/api/v1/users/u1")]
    assert all(r.headers["x-api-key"] == "gateway-key" for r in seen)
    assert b'"is_active":true' in seen[1].content.replace(b" ", b"")


async def test_ensure_user_resets_the_password_when_the_user_already_exists():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(400, json={"detail": "This username is unavailable."})
        if request.method == "GET":
            return httpx.Response(200, json={"total_count": 1, "users": [{"id": "u9", "username": "tenant-a"}]})
        return httpx.Response(200, json={})

    client, seen = _client(handler)

    assert await client.ensure_user("tenant-a", "pw") == "u9"
    assert ("PATCH", "/api/v1/users/u9/reset-password") in [(r.method, r.url.path) for r in seen]


async def test_ensure_user_fails_when_langflow_rejects_and_the_user_is_not_there():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(403, json={})
        return httpx.Response(200, json={"users": []})

    client, _ = _client(handler)
    with pytest.raises(LangflowSessionError):
        await client.ensure_user("tenant-a", "pw")


async def test_ensure_user_requires_the_api_key(monkeypatch):
    monkeypatch.setattr(settings, "LANGFLOW_API_KEY", None)
    client, _ = _client(lambda r: httpx.Response(201, json={"id": "u1"}))
    with pytest.raises(LangflowSessionError):
        await client.ensure_user("tenant-a", "pw")


async def test_login_returns_the_tokens_and_sends_a_form():
    client, seen = _client(lambda r: httpx.Response(200, json={"access_token": "a", "refresh_token": "r"}))

    tokens = await client.login("tenant-a", "pw")

    assert (tokens.access_token, tokens.refresh_token) == ("a", "r")
    assert seen[0].headers["content-type"] == "application/x-www-form-urlencoded"


async def test_login_refused_and_network_errors_become_session_errors():
    client, _ = _client(lambda r: httpx.Response(401, json={}))
    with pytest.raises(LangflowSessionError):
        await client.login("tenant-a", "bad")

    def boom(request):
        raise httpx.ConnectError("down")

    client, _ = _client(boom)
    with pytest.raises(LangflowSessionError):
        await client.login("tenant-a", "pw")


async def test_a_non_json_answer_is_reported_not_crashed_on():
    # Ruta desconocida: Langflow devuelve el index.html del SPA con 200.
    client, _ = _client(lambda r: httpx.Response(200, text="<html></html>"))
    with pytest.raises(LangflowSessionError):
        await client.login("tenant-a", "pw")


async def test_list_and_create_projects_use_the_users_own_token():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=[{"id": "f1", "name": "Ventas"}])
        return httpx.Response(201, json={"id": "f2"})

    client, seen = _client(handler)

    assert await client.list_projects("tok") == {"f1": "Ventas"}
    assert await client.create_project("tok", "Soporte") == "f2"
    assert all(r.headers["authorization"] == "Bearer tok" for r in seen)
    assert all("x-api-key" not in r.headers for r in seen)


async def test_list_flows_keeps_only_flows_of_that_folder_by_name():
    import httpx

    from app.adapters.outbound.langflow.admin_client import LangflowAdminClient

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=[
            {"id": "b", "name": "beta", "folder_id": "F1", "is_component": False},
            {"id": "a", "name": "Alpha", "folder_id": "F1", "is_component": False, "description": "d"},
            {"id": "c", "name": "Componente", "folder_id": "F1", "is_component": True},
            {"id": "x", "name": "Otra carpeta", "folder_id": "F2", "is_component": False},
        ])

    client = LangflowAdminClient(httpx.AsyncClient(base_url="http://lf", transport=httpx.MockTransport(handler)))

    flows = await client.list_flows("tok", "F1")

    assert [(f.id, f.name) for f in flows] == [("a", "Alpha"), ("b", "beta")]
    assert flows[0].description == "d"
    assert seen["params"]["folder_id"] == "F1" and seen["params"]["header_flows"] == "true"
    assert seen["auth"] == "Bearer tok"


async def test_list_flows_rejected():
    import httpx
    import pytest

    from app.adapters.outbound.langflow.admin_client import LangflowAdminClient
    from app.domain.ports.outbound import LangflowSessionError

    client = LangflowAdminClient(
        httpx.AsyncClient(base_url="http://lf", transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    )
    with pytest.raises(LangflowSessionError):
        await client.list_flows("tok", "F1")


def test_base_agent_flow_uses_the_prompt_memory_limit_and_openai_variable():
    from app.adapters.outbound.langflow.admin_client import build_base_agent_flow

    flow = build_base_agent_flow("Fibi", "Eres Fibi.")

    nodes = {n["data"]["type"]: n["data"]["node"]["template"] for n in flow["data"]["nodes"]}
    assert set(nodes) == {"ChatInput", "ChatOutput", "Memory", "Prompt", "OpenAIModel"}
    assert nodes["Prompt"]["template"]["value"] == "Eres Fibi.\n\nHistorial de la conversación:\n{memory}\n"
    assert nodes["Memory"]["n_messages"]["value"] == 20
    assert nodes["OpenAIModel"]["api_key"]["value"] == "OPENAI_API_KEY"
    assert nodes["OpenAIModel"]["api_key"]["load_from_db"] is True
    assert nodes["OpenAIModel"]["model_name"]["value"] == "gpt-4.1-mini"
    assert flow["name"] == "Fibi" and flow["endpoint_name"] is None
    assert len(flow["data"]["edges"]) == 4
    # The template file itself is never modified.
    assert build_base_agent_flow("Otro", "x")["name"] == "Otro"


async def test_create_base_flow_posts_to_the_folder_and_returns_the_id():
    import json as _json

    import httpx

    from app.adapters.outbound.langflow.admin_client import LangflowAdminClient

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(201, json={"id": "new-flow"})

    client = LangflowAdminClient(httpx.AsyncClient(base_url="http://lf", transport=httpx.MockTransport(handler)))

    flow_id = await client.create_base_flow("tok", "F1", name="Fibi", system_prompt="Eres Fibi.")

    assert flow_id == "new-flow"
    assert seen["body"]["folder_id"] == "F1" and seen["body"]["name"] == "Fibi"
    assert seen["auth"] == "Bearer tok"


async def test_list_variable_names_and_errors():
    import httpx
    import pytest

    from app.adapters.outbound.langflow.admin_client import LangflowAdminClient
    from app.domain.ports.outbound import LangflowSessionError

    ok = LangflowAdminClient(httpx.AsyncClient(base_url="http://lf", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=[{"id": "1", "name": "OPENAI_API_KEY", "type": "Credential", "value": None}])
    )))
    assert await ok.list_variable_names("tok") == ["OPENAI_API_KEY"]

    bad = LangflowAdminClient(httpx.AsyncClient(base_url="http://lf", transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    with pytest.raises(LangflowSessionError):
        await bad.list_variable_names("tok")
    with pytest.raises(LangflowSessionError):
        await bad.create_base_flow("tok", "F1", name="x", system_prompt="y")
