"""Port for a live client connection the gateway pushes JSON to (a webchat
WebSocket, a voice call's stream), so the registry that holds them doesn't
depend on the web framework."""

from __future__ import annotations

from typing import Any, Protocol


class JsonConnection(Protocol):
    """A connected client the gateway can send JSON messages to."""

    async def send_json(self, data: Any) -> None:
        """Send one JSON message.

        Args:
            data (Any): JSON-serializable message.
        """
        ...
