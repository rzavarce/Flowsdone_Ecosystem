import logging
from typing import Dict

from fastapi import WebSocket

logger = logging.getLogger("ws")


class WSRegistry:
    """
    Registry de websockets indexado por conversation_id.

    Compatibilidad:
    - websocket.py usa add(...) / remove(...)
    - HandleOutboundResponseUseCase usa send(...)
    """

    def __init__(self) -> None:
        self._connections: Dict[str, WebSocket] = {}

    def add(self, conversation_id: str, websocket: WebSocket) -> None:
        self._connections[conversation_id] = websocket
        logger.info(
            "websocket.registry.added",
            extra={"conversation_id": conversation_id},
        )

    def remove(self, conversation_id: str) -> None:
        if conversation_id in self._connections:
            self._connections.pop(conversation_id, None)
            logger.info(
                "websocket.registry.removed",
                extra={"conversation_id": conversation_id},
            )

    async def send(self, conversation_id: str, message: dict) -> None:
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