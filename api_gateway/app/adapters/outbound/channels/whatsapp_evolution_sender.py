"""WhatsApp (Evolution API) outbound channel sender."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.whatsapp_evolution.sender")


class WhatsAppEvolutionSender(ChannelSenderPort):
    """Sends messages via Evolution API.

    `external_id` is the Evolution instance name (the same value used
    for inbound webhook routing). The apikey is the shared secret of
    our own Evolution instance (settings.EVOLUTION_API_KEY), not
    something per connection.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Send a text message to a WhatsApp recipient.

        Args:
            external_id (str): Evolution API instance name.
            recipient_id (str): WhatsApp remoteJid of the recipient.
            text (str): Message body to send.
            credentials (Dict[str, Any]): Unused for WhatsApp; kept for
                interface consistency with ChannelSenderPort.
        """
        if not settings.EVOLUTION_API_KEY:
            logger.error(
                "channel.sender.missing_credentials",
                extra={"channel": "whatsapp_evolution", "external_id": external_id},
            )
            return

        url = f"{settings.EVOLUTION_API_BASE_URL}/message/sendText/{external_id}"

        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                headers={"apikey": settings.EVOLUTION_API_KEY},
                json={"number": recipient_id, "text": text},
            )

        if response.status_code >= 400:
            logger.error(
                "channel.sender.failed",
                extra={
                    "channel": "whatsapp_evolution",
                    "external_id": external_id,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            return

        logger.info(
            "channel.sender.sent",
            extra={"channel": "whatsapp_evolution", "external_id": external_id},
        )
