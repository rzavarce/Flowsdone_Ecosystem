"""Chatwoot outbound channel sender (Facebook / Instagram via Chatwoot)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.adapters.outbound.channels.chatwoot_api import ChatwootClient, ChatwootError
from app.domain.ports.outbound import ChannelAppRepositoryPort, ChannelSenderPort

logger = logging.getLogger("channels.chatwoot.sender")


class ChatwootSender(ChannelSenderPort):
    """Replies in a Chatwoot conversation as the SaaS's Agent Bot;
    Chatwoot delivers it to Messenger or Instagram.
    """

    def __init__(self, channel_app_repo: Optional[ChannelAppRepositoryPort]) -> None:
        """Build the sender.

        Args:
            channel_app_repo (Optional[ChannelAppRepositoryPort]): Where the
                "chatwoot" channel_app lives.
        """
        self._client = ChatwootClient(channel_app_repo)

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a text message to a Chatwoot conversation.

        Args:
            external_id (str): The Chatwoot inbox id, used only for logging.
            recipient_id (str): The Chatwoot conversation id (the
                conversation key the inbound webhook used).
            text (str): Message body to send.
            credentials (Dict[str, Any]): Unused (the shared app holds them).
            config (Optional[Dict[str, Any]]): Unused by this channel.
        """
        try:
            await self._client.send_message(recipient_id, text)
        except ChatwootError:
            logger.exception("channel.sender.failed", extra={"channel": "chatwoot", "external_id": external_id})
            return
        logger.info("channel.sender.sent", extra={"channel": "chatwoot", "external_id": external_id})
