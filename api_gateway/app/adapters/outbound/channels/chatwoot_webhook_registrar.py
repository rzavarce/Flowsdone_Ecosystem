"""Chatwoot inbox registration: hand an inbox's conversations to Flowsdone."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.adapters.outbound.channels.chatwoot_api import BOT_ID_FIELD, ChatwootClient
from app.domain.ports.outbound import ChannelAppRepositoryPort

logger = logging.getLogger("channels.chatwoot.webhook_registrar")


class ChatwootWebhookRegistrar:
    """Assigns the SaaS's Agent Bot to a Chatwoot inbox (creating the bot
    the first time), so Chatwoot starts sending that inbox's messages to
    our webhook.

    The webhook is authenticated with the shared app's `webhook_token`,
    not with a per-connection secret, so `secret_field` is None.
    """

    secret_field = None

    def __init__(self, channel_app_repo: Optional[ChannelAppRepositoryPort]) -> None:
        """Build the registrar.

        Args:
            channel_app_repo (Optional[ChannelAppRepositoryPort]): Where the
                "chatwoot" channel_app lives.
        """
        self._client = ChatwootClient(channel_app_repo)

    async def register(
        self, *, external_id: str, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Assign the Agent Bot to the inbox.

        Args:
            external_id (str): The Chatwoot inbox id.
            credentials (Dict[str, Any]): Unused (the shared app holds them).
            config (Optional[Dict[str, Any]]): Unused by this channel.

        Raises:
            ChatwootError: If the Chatwoot app is not configured or
                Chatwoot rejects the call.
        """
        app = await self._client.ensure_bot()
        await self._client.set_inbox_bot(external_id, app.config[BOT_ID_FIELD])
        logger.info("channel.webhook_registrar.registered", extra={"channel": "chatwoot", "inbox_id": external_id})

    async def deregister(
        self, *, external_id: str, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Remove the Agent Bot from the inbox.

        Args:
            external_id (str): The Chatwoot inbox id.
            credentials (Dict[str, Any]): Unused.
            config (Optional[Dict[str, Any]]): Unused by this channel.

        Raises:
            ChatwootError: If the Chatwoot app is not configured or
                Chatwoot rejects the call.
        """
        await self._client.set_inbox_bot(external_id, None)
