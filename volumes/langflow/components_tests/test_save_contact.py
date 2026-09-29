"""Tests for SaveContactComponent in save_contact.py.

Same isolation approach as the sibling test files: stubs `langflow.*` and
`httpx` instead of importing the real packages, and replays scripted
gateway responses.

Run directly with:
    pytest volumes/langflow/components_tests/test_save_contact.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

CONVERSATION_ID = "5f0c6a52-2d4e-4c1b-9d3a-6f1e2a7b8c90"


class _FakeRequestError(Exception):
    """Stand-in for httpx.RequestError (network-level failures)."""


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json body")
        return self._json_data


class _FakeAsyncClient:
    """Replays a scripted sequence of responses/exceptions, one per call to .post()."""

    next_script = []
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).calls.append({"url": url, "json": json, "headers": headers})
        step = type(self).next_script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

    class Component:
        def set(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            return self

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

    langflow = types.ModuleType("langflow")
    langflow_custom = types.ModuleType("langflow.custom")
    langflow_custom.Component = Component
    langflow_io = types.ModuleType("langflow.io")
    for name in ("IntInput", "MultilineInput", "Output", "SecretStrInput", "StrInput"):
        setattr(langflow_io, name, type(name, (_InputBase,), {}))
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data

    httpx_module = types.ModuleType("httpx")
    httpx_module.AsyncClient = _FakeAsyncClient
    httpx_module.RequestError = _FakeRequestError

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["httpx"] = httpx_module


_install_stubs()

_MODULE_PATH = Path(__file__).parent.parent / "components" / "flowsdone" / "save_contact.py"
_spec = importlib.util.spec_from_file_location("save_contact", _MODULE_PATH)
save_contact = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(save_contact)

SaveContactComponent = save_contact.SaveContactComponent


def _make_component(session_id=CONVERSATION_ID, monkeypatch=None, **args):
    _FakeAsyncClient.next_script = []
    _FakeAsyncClient.calls = []
    component = SaveContactComponent()
    component.graph = types.SimpleNamespace(session_id=session_id)
    component.gateway_url = ""
    component.timeout = 10
    component.set(contact_name="", contact_email="", contact_phone="")
    component.set(**args)
    return component


def _run(component):
    return asyncio.run(component.save_contact()).data


def _env(monkeypatch):
    monkeypatch.setenv("GATEWAY_INTERNAL_URL", "http://api_gateway:8000/")
    monkeypatch.setenv("GATEWAY_ADMIN_API_KEY", "admin-key")


def test_saves_what_the_customer_said_on_the_conversations_card(monkeypatch):
    _env(monkeypatch)
    component = _make_component(contact_name="  Ana   Pérez ", contact_email="ana@example.com")
    _FakeAsyncClient.next_script = [_FakeResponse(200, {"name": "Ana Pérez", "email": "ana@example.com"})]

    result = _run(component)

    [call] = _FakeAsyncClient.calls
    assert call["url"] == f"http://api_gateway:8000/internal/admin/conversations/{CONVERSATION_ID}/contact/capture"
    assert call["json"] == {"name": "Ana Pérez", "email": "ana@example.com"}
    assert call["headers"] == {"X-Admin-Api-Key": "admin-key"}
    assert result["success"] is True and result["contact"]["name"] == "Ana Pérez"


def test_arguments_do_not_leak_into_the_next_call(monkeypatch):
    _env(monkeypatch)
    component = _make_component(contact_name="Ana", contact_phone="600111222")
    _FakeAsyncClient.next_script = [_FakeResponse(200, {}), _FakeResponse(200, {})]
    _run(component)

    component.set(contact_email="ana@example.com")
    _run(component)

    assert _FakeAsyncClient.calls[1]["json"] == {"email": "ana@example.com"}


def test_nothing_to_save_is_told_to_the_agent(monkeypatch):
    _env(monkeypatch)
    result = _run(_make_component(contact_name="   "))

    assert result["success"] is False and "al menos" in result["error"]
    assert _FakeAsyncClient.calls == []


def test_test_runs_without_a_conversation_do_not_call_the_gateway(monkeypatch):
    _env(monkeypatch)
    result = _run(_make_component(session_id="test:agent:visitor", contact_name="Ana"))

    assert result["success"] is True and "skipped" in result
    assert _FakeAsyncClient.calls == []


def test_an_unregistered_conversation_is_skipped(monkeypatch):
    _env(monkeypatch)
    component = _make_component(contact_name="Ana")
    _FakeAsyncClient.next_script = [_FakeResponse(404, {"detail": "not found"})]

    result = _run(component)

    assert result["success"] is True and "skipped" in result


def test_an_invalid_value_asks_the_agent_to_repeat_it(monkeypatch):
    _env(monkeypatch)
    component = _make_component(contact_email="ana(at)example")
    _FakeAsyncClient.next_script = [_FakeResponse(422, {"detail": "email is not valid"})]

    result = _run(component)

    assert result["success"] is False
    assert "email is not valid" in result["error"] and "repita" in result["error"]


def test_gateway_errors_and_missing_configuration_are_reported(monkeypatch):
    _env(monkeypatch)
    component = _make_component(contact_name="Ana")
    _FakeAsyncClient.next_script = [_FakeRequestError("connection refused")]
    assert "No se pudo conectar" in _run(component)["error"]

    component.set(contact_name="Ana")
    _FakeAsyncClient.next_script = [_FakeResponse(500, text="boom")]
    assert "HTTP 500" in _run(component)["error"]

    monkeypatch.delenv("GATEWAY_ADMIN_API_KEY")
    component.set(contact_name="Ana")
    assert "no está configurado" in _run(component)["error"]
