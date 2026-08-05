"""Reusable double for monkeypatching `httpx.AsyncClient` in adapter
tests, so outbound HTTP calls (Telegram Bot API, Meta Graph API,
Evolution API, ...) never hit the real network.

Usage in a test::

    def test_something(monkeypatch):
        fake_client = FakeAsyncClient(lambda call: FakeResponse(200, json_body={"ok": True}))
        monkeypatch.setattr(telegram_webhook_registrar.httpx, "AsyncClient", fake_client.as_constructor())
        ...
        assert fake_client.calls[0].method == "POST"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class FakeResponse:
    """Stand-in for `httpx.Response`, covering only what this codebase reads."""

    status_code: int = 200
    json_body: Optional[Dict[str, Any]] = None
    text: str = ""
    headers: Dict[str, str] = field(
        default_factory=lambda: {"content-type": "application/json"}
    )

    def json(self) -> Dict[str, Any]:
        return self.json_body if self.json_body is not None else {}


@dataclass
class RecordedCall:
    """One HTTP call made through a FakeAsyncClient."""

    method: str
    url: str
    kwargs: Dict[str, Any]


class FakeAsyncClient:
    """Drop-in async-context-manager stand-in for `httpx.AsyncClient`.

    Records every call and answers with whatever `response_factory`
    returns (or raises, to simulate a network failure).
    """

    def __init__(self, response_factory: Callable[[RecordedCall], FakeResponse]) -> None:
        self._response_factory = response_factory
        self.calls: List[RecordedCall] = []

    def as_constructor(self) -> Callable[..., "FakeAsyncClient"]:
        """Return a callable usable as a replacement for `httpx.AsyncClient`.

        `httpx.AsyncClient(timeout=...)` is called with kwargs the
        adapters don't need faked (e.g. `timeout`); this callable
        accepts and discards them, always returning `self`, so every
        call in a test is recorded on the same instance.
        """

        def _constructor(*_args: Any, **_kwargs: Any) -> "FakeAsyncClient":
            return self

        return _constructor

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        call = RecordedCall(method=method, url=url, kwargs=kwargs)
        self.calls.append(call)
        return self._response_factory(call)

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        return await self.request("POST", url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return await self.request("GET", url, **kwargs)
