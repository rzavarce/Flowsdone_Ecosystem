"""Tests for LangfuseUsageSource (Langfuse API faked)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.adapters.outbound.langfuse import usage_source as module
from app.adapters.outbound.langfuse.usage_source import LangfuseApiError, LangfuseUsageSource
from api_gateway.tests.support.fake_httpx import FakeAsyncClient, FakeResponse

pytestmark = pytest.mark.anyio

START = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 1, 13, 0, tzinfo=timezone.utc)


def _observation(id, trace_id, **extra):
    base = {
        "id": id, "traceId": trace_id, "model": "gpt-4.1-mini-2025-04-14", "startTime": "2026-09-01T12:10:00.000Z",
        "usageDetails": {"input": 500, "output": 40, "total": 540},
    }
    base.update(extra)
    return base


def _source(monkeypatch, responder):
    fake = FakeAsyncClient(responder)
    captured = {}

    def constructor(*args, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr(module.httpx, "AsyncClient", constructor)
    return LangfuseUsageSource(base_url="http://lf:3000/", public_key="pk", secret_key="sk"), fake, captured


async def test_reads_all_pages_and_resolves_each_trace_session_once(monkeypatch):
    pages = {
        1: {"data": [_observation("o1", "t1"), _observation("o2", "t1")], "meta": {"totalPages": 2}},
        2: {"data": [_observation("o3", "t2", model=None), _observation("o4", "t2")], "meta": {"totalPages": 2}},
    }

    def respond(call):
        if call.url == "/api/public/observations":
            return FakeResponse(200, json_body=pages[call.kwargs["params"]["page"]])
        return FakeResponse(200, json_body={"sessionId": f"session-of-{call.url.rsplit('/', 1)[-1]}"})

    source, fake, captured = _source(monkeypatch, respond)

    generations = await source.list_generations(start=START, end=END)

    assert [g.id for g in generations] == ["o1", "o2", "o4"]  # o3 has no model
    assert [g.session_id for g in generations] == ["session-of-t1", "session-of-t1", "session-of-t2"]
    trace_calls = [c.url for c in fake.calls if c.url.startswith("/api/public/traces/")]
    assert trace_calls == ["/api/public/traces/t1", "/api/public/traces/t2"]
    first_params = fake.calls[0].kwargs["params"]
    assert first_params["type"] == "GENERATION"
    assert first_params["fromStartTime"] == "2026-09-01T12:00:00.000Z"
    assert first_params["toStartTime"] == "2026-09-01T13:00:00.000Z"
    assert captured["auth"] == ("pk", "sk") and captured["base_url"] == "http://lf:3000"
    assert generations[0].start_time == datetime(2026, 9, 1, 12, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("observation,expected", [
    (_observation("o", "t"), (500, 40, 0)),
    (_observation("o", "t", usageDetails={"input": 300, "output": 5, "input_cached_tokens": 200}), (300, 5, 200)),
    (_observation("o", "t", usageDetails={"input": 1, "output": 1, "cache_read_input_tokens": 7}), (1, 1, 7)),
    (_observation("o", "t", usageDetails=None, usage={"input": 9, "output": 3}), (9, 3, 0)),
])
async def test_token_counts(monkeypatch, observation, expected):
    def respond(call):
        if call.url == "/api/public/observations":
            return FakeResponse(200, json_body={"data": [observation], "meta": {"totalPages": 1}})
        return FakeResponse(200, json_body={"sessionId": "s"})

    source, _, _ = _source(monkeypatch, respond)

    [generation] = await source.list_generations(start=START, end=END)

    assert (generation.input_tokens, generation.output_tokens, generation.cached_input_tokens) == expected


async def test_a_missing_trace_leaves_the_session_empty(monkeypatch):
    def respond(call):
        if call.url == "/api/public/observations":
            return FakeResponse(200, json_body={"data": [_observation("o1", "gone")], "meta": {"totalPages": 1}})
        return FakeResponse(404, text="not found")

    source, _, _ = _source(monkeypatch, respond)

    [generation] = await source.list_generations(start=START, end=END)

    assert generation.session_id is None


async def test_api_errors_on_observations_raise(monkeypatch):
    source, _, _ = _source(monkeypatch, lambda call: FakeResponse(401, text="unauthorized"))

    with pytest.raises(LangfuseApiError):
        await source.list_generations(start=START, end=END)
