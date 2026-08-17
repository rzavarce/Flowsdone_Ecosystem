"""In-memory registry of live WebSocket connections."""

import logging
from typing import Dict

from fastapi import WebSocket

logger = logging.getLogger("ws")


class WSRegistry:
    """Tracks live WebSocket connections keyed by conversation_id.

    Used by websocket.py (add/remove, on connect/disconnect) and by
    HandleOutboundResponseUseCase (send, to push a workflow response to
    the client).
    """

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}

    def add(self, conversation_id: str, websocket: WebSocket) -> None:
        """Register a connected WebSocket for a conversation.

        Args:
            conversation_id (str): Id of the conversation.
            websocket (WebSocket): The connected WebSocket instance.
        """
        self._connections[conversation_id] = websocket
        logger.info(
            "websocket.registry.added",
            extra={"conversation_id": conversation_id},
        )

    def remove(self, conversation_id: str) -> None:
        """Unregister a conversation's WebSocket, if present.

        Args:
            conversation_id (str): Id of the conversation.
        """
        if conversation_id in self._connections:
            self._connections.pop(conversation_id, None)
            logger.info(
                "websocket.registry.removed",
                extra={"conversation_id": conversation_id},
            )

    async def send(self, conversation_id: str, message: dict) -> None:
        """Send a JSON message to a conversation's WebSocket, if connected.

        Silently no-ops if there is no live connection for the
        conversation (e.g. the message came from a native channel, not
        webchat). Removes the connection if sending fails.

        Args:
            conversation_id (str): Id of the conversation.
            message (dict): JSON-serializable message to send.
        """
        websocket = self._connections.get(conversation_id)

        if not websocket:
            logger.warning(
                "websocket.not_found",
                extra={"conversation_id": conversation_id},
            )
            return

        try:
            await websocket.send_json(message)
            logger.info(
                "websocket.message.sent",
                extra={"conversation_id": conversation_id},
            )
        except Exception:
            logger.error(
                "websocket.send.failed",
                extra={"conversation_id": conversation_id},
                exc_info=True,
            )
            self.remove(conversation_id)
