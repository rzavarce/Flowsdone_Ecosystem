"""Tests for WSRegistry."""

from __future__ import annotations

from typing import Any, List

import pytest

from app.application.services.ws_registry import WSRegistry

pytestmark = pytest.mark.anyio


class FakeWebSocket:
    """Minimal stand-in for FastAPI's WebSocket, only what WSRegistry uses."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: List[Any] = []

    async def send_json(self, message: dict) -> None:
        if self.fail:
            raise RuntimeError("connection closed")
        self.sent.append(message)


async def test_send_delivers_to_registered_connection():
    registry = WSRegistry()
    ws = FakeWebSocket()
    registry.add("conv-1", ws)

    await registry.send("conv-1", {"type": "chat.response"})

    assert ws.sent == [{"type": "chat.response"}]


async def test_send_is_a_noop_for_unknown_conversation():
    registry = WSRegistry()

    # Should not raise even though nothing is registered.
    await registry.send("unknown", {"type": "chat.response"})


async def test_remove_unregisters_a_connection():
    registry = WSRegistry()
    ws = FakeWebSocket()
    registry.add("conv-1", ws)

    registry.remove("conv-1")
    await registry.send("conv-1", {"type": "chat.response"})

    assert ws.sent == []


async def test_remove_unknown_conversation_is_a_noop():
    registry = WSRegistry()

    # Should not raise.
    registry.remove("never-added")


async def test_send_failure_self_heals_by_removing_the_dead_connection():
    registry = WSRegistry()
    ws = FakeWebSocket(fail=True)
    registry.add("conv-1", ws)

    # First send fails and should silently remove the dead connection...
    await registry.send("conv-1", {"type": "chat.response"})

    # ...so a second send is a clean no-op rather than retrying the same
    # broken socket.
    ws.fail = False
    await registry.send("conv-1", {"type": "chat.response"})
    assert ws.sent == []
