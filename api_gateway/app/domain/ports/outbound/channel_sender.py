"""Port for sending a message back to a native chat channel."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class ChannelSenderPort(Protocol):
    """Sends a message to a native channel (WhatsApp, Facebook, Instagram,
    Telegram, X, TikTok, etc.) using the credentials of the channel
    connection that originated the conversation.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a text message to a channel.

        Args:
            external_id (str): Channel-specific sender identifier (page
                id, Evolution instance name, bot token, etc.).
            recipient_id (str): Id of the recipient on the external platform.
            text (str): Message body to send.
            credentials (Dict[str, Any]): Decrypted channel credentials
                required to send.
            config (Optional[Dict[str, Any]]): The connection's
                non-secret configuration (e.g. which API environment
                to use), for the channels that need it.
        """
        ...
