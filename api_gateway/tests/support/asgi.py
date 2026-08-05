"""Helper to exercise a single inbound webhook router end to end (HTTP
in, HTTP out) over ASGI, with fakes wired into `app.state` instead of
a real database/broker.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx
from fastapi import APIRouter, FastAPI


@asynccontextmanager
async def client_for_router(router: APIRouter, **state: Any) -> AsyncIterator[httpx.AsyncClient]:
    """Build a minimal FastAPI app around `router` and yield an
    httpx.AsyncClient talking to it in-process (no real socket).

    Args:
        router (APIRouter): The single router under test (e.g. the
            Telegram or Facebook webhook router).
        **state (Any): Attributes to set on `app.state` (e.g.
            `channel_connection_repo=fake_repo`), matching whatever the
            router's handlers read off `request.app.state`.

    Yields:
        httpx.AsyncClient: A client whose requests reach `router`
        in-process.
    """
    app = FastAPI()
    app.include_router(router)
    for key, value in state.items():
        setattr(app.state, key, value)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
