"""Tests for LangflowExecutor."""

from __future__ import annotations

import pytest

from app.adapters.outbound.langflow import executor as module
from app.adapters.outbound.langflow.executor import LangflowExecutionError, LangflowExecutor
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio


def _patch_client(monkeypatch, response: FakeResponse) -> FakeAsyncClient:
    fake_client = FakeAsyncClient(lambda call: response)
    monkeypatch.setattr(module.httpx, "AsyncClient", fake_client.as_constructor())
    return fake_client


async def test_run_requests_full_graph_so_side_effect_branches_execute(monkeypatch):
    """Regression guard: output_type must be "any", not "chat".

    Langflow only builds the vertices required to produce the requested
    output_type. "chat" prunes any branch that doesn't feed the flow's
    Chat Output component, so a flow with a side-effect-only branch (e.g.
    an HTTP call fired after a conditional check, never wired back into
    Chat Output) would silently never execute that branch.
    """
    fake_client = _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    await LangflowExecutor().run(
        workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1"
    )

    sent = fake_client.calls[0]
    assert sent.kwargs["json"]["output_type"] == "any"
    assert sent.kwargs["json"]["input_type"] == "chat"


async def test_run_sends_message_as_input_value_and_forwards_session_id(monkeypatch):
    fake_client = _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    await LangflowExecutor().run(
        workflow_id="flow-1",
        payload={"message": "hola, quiero info"},
        conversation_id="conv-42",
    )

    sent = fake_client.calls[0]
    assert sent.url == "/api/v1/run/flow-1"
    assert sent.kwargs["json"]["input_value"] == "hola, quiero info"
    assert sent.kwargs["json"]["session_id"] == "conv-42"


async def test_run_serializes_payload_without_message_key_as_input_value(monkeypatch):
    fake_client = _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    await LangflowExecutor().run(
        workflow_id="flow-1", payload={"raw": {"foo": "bar"}}, conversation_id="conv-1"
    )

    sent = fake_client.calls[0]
    assert sent.kwargs["json"]["input_value"] == '{"raw": {"foo": "bar"}}'


async def test_run_returns_parsed_json_on_success(monkeypatch):
    _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    result = await LangflowExecutor().run(
        workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1"
    )

    assert result == {"result": "ok"}


async def test_run_returns_none_on_empty_success_body(monkeypatch):
    _patch_client(monkeypatch, FakeResponse(200, content=b"", text=""))

    result = await LangflowExecutor().run(
        workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1"
    )

    assert result is None


async def test_run_raises_on_http_error_status(monkeypatch):
    _patch_client(
        monkeypatch,
        FakeResponse(500, json_body={"detail": "boom"}, text='{"detail": "boom"}'),
    )

    with pytest.raises(LangflowExecutionError) as exc_info:
        await LangflowExecutor().run(
            workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1"
        )

    assert exc_info.value.status_code == 500
    assert "boom" in str(exc_info.value)


async def test_run_raises_on_non_json_2xx_response(monkeypatch):
    """Langflow 1.4 answers every 404 (unknown workflow, or a flow that
    fails mid-run on a missing global variable) with its index.html and
    status 200: that must not be treated as a successful run, and the
    error must point at the likely cause.
    """
    _patch_client(
        monkeypatch,
        FakeResponse(
            200,
            text="<!doctype html><html>...</html>",
            content=b"<!doctype html><html>...</html>",
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )

    with pytest.raises(LangflowExecutionError) as exc_info:
        await LangflowExecutor().run(
            workflow_id="nonexistent-flow", payload={"message": "hola"}, conversation_id="conv-1"
        )

    assert exc_info.value.status_code == 404
    assert "global variable" in str(exc_info.value)
    assert "LANGFLOW_API_KEY" in str(exc_info.value)


async def test_run_uses_the_given_api_key_for_this_call(monkeypatch):
    """A tenant's flow runs with the tenant's key, so Langflow resolves the
    flow's global variables for the tenant's user."""
    fake_client = _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    await LangflowExecutor().run(
        workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1", api_key="sk-tenant"
    )

    assert fake_client.calls[0].kwargs["headers"] == {"x-api-key": "sk-tenant"}


async def test_run_without_api_key_keeps_the_platform_key(monkeypatch):
    fake_client = _patch_client(monkeypatch, FakeResponse(200, json_body={"result": "ok"}))

    await LangflowExecutor().run(workflow_id="flow-1", payload={"message": "hola"}, conversation_id="conv-1")

    assert fake_client.calls[0].kwargs["headers"] is None
