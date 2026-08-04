from __future__ import annotations

from typing import Any, Dict, Protocol


class ChannelSenderPort(Protocol):
    """
    Envía un mensaje de vuelta a un canal nativo (WhatsApp, Facebook,
    Instagram, Telegram, X, TikTok, ...) usando las credenciales del
    channel_connection que originó la conversación.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None: ...
