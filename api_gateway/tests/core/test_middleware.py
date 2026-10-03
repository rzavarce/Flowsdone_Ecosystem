"""Tests for CorrelationIdMiddleware: propagates or creates X-Correlation-ID."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from app.core.context import correlation_id_ctx
from app.core.middleware import CORRELATION_HEADER, CorrelationIdMiddleware

pytestmark = pytest.mark.anyio


def _app():
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/ping")
    async def ping():
        return {"seen": correlation_id_ctx.get()}

    return app


async def _get(headers=None):
    transport = httpx.ASGITransport(app=_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/ping", headers=headers or {})


async def test_an_incoming_correlation_id_is_kept_and_visible_to_the_handler():
    response = await _get({CORRELATION_HEADER: "abc-123"})

    assert response.headers[CORRELATION_HEADER] == "abc-123"
    assert response.json() == {"seen": "abc-123"}


async def test_a_new_correlation_id_is_created_when_missing():
    response = await _get()

    generated = response.headers[CORRELATION_HEADER]
    assert len(generated) == 36 and response.json() == {"seen": generated}


@pytest.mark.parametrize("unsafe", ["x" * 129, "abc\nINFO forged line", "id with spaces"])
async def test_an_unsafe_incoming_correlation_id_is_replaced(unsafe):
    response = await _get({CORRELATION_HEADER: unsafe})

    generated = response.headers[CORRELATION_HEADER]
    assert generated != unsafe and len(generated) == 36


async def test_healthcheck_paths_are_not_access_logged(caplog):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ping")
    async def ping():
        return {}

    transport = httpx.ASGITransport(app=app)
    with caplog.at_level("INFO", logger="api"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/health")
            await client.get("/ping")

    paths = [r.path for r in caplog.records if r.getMessage() == "request.completed"]
    assert paths == ["/ping"]
