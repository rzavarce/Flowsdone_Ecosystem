"""Tests for ResilientHTTPRequestComponent in http_request_resilient.py.

Same isolation approach as the sibling test files: stubs `langflow.*` and
`httpx` instead of importing the real packages. Focused on the actual
policy this component exists for: which failures get retried, which fail
immediately, backoff timing, Retry-After handling, and the
raise_on_failure switch.

Run directly with:
    pytest volumes/langflow/components_tests/test_http_request_resilient.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path


class _FakeRequestError(Exception):
    """Stand-in for httpx.RequestError (network-level failures)."""


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text="", headers=None, url="http://x"):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.url = url

    def json(self):
        if self._json_data is None:
            raise ValueError("no json body")
        return self._json_data


class _FakeAsyncClient:
    """Replays a scripted sequence of responses/exceptions, one per call to .request()."""

    next_script = []  # list of _FakeResponse instances or exception instances
    calls = []
    sleeps = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def request(self, method, url, headers=None, params=None, json=None):
        type(self).calls.append({"method": method, "url": url, "headers": headers, "params": params, "json": json})
        step = type(self).next_script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


async def _fake_sleep(seconds):
    _FakeAsyncClient.sleeps.append(seconds)


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

    class Component:
        pass

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class StrInput(_InputBase):
        pass

    class SecretStrInput(_InputBase):
        pass

    class IntInput(_InputBase):
        pass

    class FloatInput(_InputBase):
        pass

    class BoolInput(_InputBase):
        pass

    class DropdownInput(_InputBase):
        pass

    class Output(_InputBase):
        pass

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

    httpx_module = types.ModuleType("httpx")
    httpx_module.AsyncClient = _FakeAsyncClient
    httpx_module.RequestError = _FakeRequestError
    httpx_module.Response = _FakeResponse

    langflow = types.ModuleType("langflow")
    langflow_custom = types.ModuleType("langflow.custom")
    langflow_custom.Component = Component
    langflow_io = types.ModuleType("langflow.io")
    langflow_io.StrInput = StrInput
    langflow_io.SecretStrInput = SecretStrInput
    langflow_io.IntInput = IntInput
    langflow_io.FloatInput = FloatInput
    langflow_io.BoolInput = BoolInput
    langflow_io.DropdownInput = DropdownInput
    langflow_io.Output = Output
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["httpx"] = httpx_module


_install_stubs()

_MODULE_PATH = Path(__file__).parent.parent / "components" / "http_request_resilient.py"
_spec = importlib.util.spec_from_file_location("http_request_resilient", _MODULE_PATH)
http_request_resilient = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(http_request_resilient)

# The component calls asyncio.sleep directly (imported as `asyncio` inside the
# module), so patch it there rather than reaching into the stdlib globally.
http_request_resilient.asyncio.sleep = _fake_sleep

ResilientHTTPRequestComponent = http_request_resilient.ResilientHTTPRequestComponent


def _reset():
    _FakeAsyncClient.next_script = []
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.sleeps = []


def _make_component(**overrides):
    component = ResilientHTTPRequestComponent()
    component.url = "http://erp.fibralan.com/api/productos"
    component.method = "GET"
    component.headers_json = ""
    component.query_params_json = ""
    component.body_json = ""
    component.bearer_token = ""
    component.timeout = 10
    component.max_retries = 3
    component.retry_backoff_base = 0.5
    component.retry_backoff_max = 8.0
    component.retryable_status_codes = "429,500,502,503,504"
    component.retry_on_network_error = True
    component.respect_retry_after = True
    component.raise_on_failure = False
    for key, value in overrides.items():
        setattr(component, key, value)
    return component


def test_succeeds_on_first_try_without_retrying():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(200, json_data={"ok": True})]
    component = _make_component()

    result = asyncio.run(component.make_request())

    assert result.data["success"] is True
    assert result.data["data"] == {"ok": True}
    assert result.data["attempts"] == 1
    assert _FakeAsyncClient.sleeps == []


def test_retries_on_503_then_succeeds():
    _reset()
    _FakeAsyncClient.next_script = [
        _FakeResponse(503, text="service unavailable"),
        _FakeResponse(200, json_data={"ok": True}),
    ]
    component = _make_component()

    result = asyncio.run(component.make_request())

    assert result.data["success"] is True
    assert result.data["attempts"] == 2
    assert len(_FakeAsyncClient.sleeps) == 1


def test_does_not_retry_404():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(404, text="not found")]
    component = _make_component()

    result = asyncio.run(component.make_request())

    assert result.data["success"] is False
    assert result.data["status_code"] == 404
    assert result.data["attempts"] == 1
    assert _FakeAsyncClient.sleeps == []


def test_does_not_retry_403():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(403, text="forbidden")]
    component = _make_component()

    result = asyncio.run(component.make_request())

    assert result.data["success"] is False
    assert result.data["status_code"] == 403
    assert _FakeAsyncClient.sleeps == []


def test_exhausts_retries_and_returns_failure_envelope_by_default():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(500)] * 4  # 1 try + 3 retries, all fail
    component = _make_component(max_retries=3)

    result = asyncio.run(component.make_request())

    assert result.data["success"] is False
    assert result.data["attempts"] == 4
    assert len(_FakeAsyncClient.sleeps) == 3


def test_raise_on_failure_true_raises_after_exhausting_retries():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(500)] * 2
    component = _make_component(max_retries=1, raise_on_failure=True)

    try:
        asyncio.run(component.make_request())
    except ValueError as exc:
        assert "2 intento" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_network_error_is_retried_when_enabled():
    _reset()
    _FakeAsyncClient.next_script = [_FakeRequestError("boom"), _FakeResponse(200, json_data={"ok": True})]
    component = _make_component()

    result = asyncio.run(component.make_request())

    assert result.data["success"] is True
    assert result.data["attempts"] == 2


def test_network_error_not_retried_when_disabled():
    _reset()
    _FakeAsyncClient.next_script = [_FakeRequestError("boom")]
    component = _make_component(retry_on_network_error=False)

    result = asyncio.run(component.make_request())

    assert result.data["success"] is False
    assert result.data["status_code"] is None
    assert _FakeAsyncClient.sleeps == []


def test_backoff_is_exponential_and_capped():
    component = _make_component(retry_backoff_base=0.5, retry_backoff_max=8.0)

    assert component._compute_backoff(1) == 0.5
    assert component._compute_backoff(2) == 1.0
    assert component._compute_backoff(3) == 2.0
    assert component._compute_backoff(10) == 8.0


def test_respects_retry_after_header_over_computed_backoff():
    _reset()
    _FakeAsyncClient.next_script = [
        _FakeResponse(429, headers={"Retry-After": "5"}),
        _FakeResponse(200, json_data={"ok": True}),
    ]
    component = _make_component(retry_backoff_base=0.1)

    asyncio.run(component.make_request())

    assert _FakeAsyncClient.sleeps == [5.0]


def test_custom_retryable_status_codes_are_honored():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(408), _FakeResponse(200, json_data={"ok": True})]
    component = _make_component(retryable_status_codes="408,429,500,502,503,504")

    result = asyncio.run(component.make_request())

    assert result.data["success"] is True
    assert result.data["attempts"] == 2


def test_bearer_token_is_added_to_headers():
    _reset()
    _FakeAsyncClient.next_script = [_FakeResponse(200, json_data={})]
    component = _make_component(bearer_token="secreta")

    asyncio.run(component.make_request())

    assert _FakeAsyncClient.calls[0]["headers"]["Authorization"] == "Bearer secreta"


def test_invalid_headers_json_raises_value_error():
    component = _make_component(headers_json="{not json")

    try:
        asyncio.run(component.make_request())
    except ValueError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
