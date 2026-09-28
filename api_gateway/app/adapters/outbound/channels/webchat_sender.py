"""Web chat outbound "sender"."""

from __future__ import annotations

from typing import Any, Dict

from app.domain.ports.outbound import ChannelSenderPort


class WebchatSender(ChannelSenderPort):
    """The web chat's replies reach the browser over its own WebSocket:
    HandleOutboundResponseUseCase.deliver() pushes them through WSRegistry,
    where the socket is registered under the conversation's session id.

    So there is nothing to send here. It still exists so the webchat is a
    channel like any other: deliver() finds a sender and records the
    outbound turn in the conversation (history, counters, archive).
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """No-op: already delivered over the WebSocket (see the class).

        Args:
            external_id (str): The channel's public key.
            recipient_id (str): The visitor.
            text (str): The reply.
            credentials (Dict[str, Any]): Unused (the web chat has none).
        """
        return None
