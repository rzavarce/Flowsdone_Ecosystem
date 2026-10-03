"""WhatsApp (360dialog, official Cloud API) outbound channel sender."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.adapters.outbound.channels.d360_api import API_KEY_FIELD, messages_url
from app.core.config import settings
from app.domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.whatsapp_360dialog.sender")

CHANNEL = "whatsapp_360dialog"


class WhatsApp360DialogSender(ChannelSenderPort):
    """Sends free-form text messages through 360dialog.

    Free-form text is only accepted by WhatsApp inside the 24h window
    opened by the contact's last message; outside it the API answers
    with an error, which is logged like any other failed delivery.
    Template messages (needed outside the window) are not sent here.
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
        """Send a text message to a WhatsApp recipient.

        Args:
            external_id (str): The business number of the connection,
                used only for logging.
            recipient_id (str): The contact's WhatsApp id (wa_id, the
                number in digits).
            text (str): Message body to send.
            credentials (Dict[str, Any]): Must contain "api_key" (the
                number's D360-API-KEY).
            config (Optional[Dict[str, Any]]): The connection's
                configuration; {"sandbox": true} targets the sandbox host.
        """
        api_key = credentials.get(API_KEY_FIELD)
        if not api_key:
            logger.error(
                "channel.sender.missing_credentials",
                extra={"channel": CHANNEL, "external_id": external_id},
            )
            return

        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(
                    messages_url(config or {}),
                    headers={"D360-API-KEY": api_key},
                    json={
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": recipient_id,
                        "type": "text",
                        "text": {"body": text},
                    },
                )
            except httpx.HTTPError:
                logger.exception(
                    "channel.sender.request_failed",
                    extra={"channel": CHANNEL, "external_id": external_id},
                )
                return

        if response.status_code >= 400:
            logger.error(
                "channel.sender.failed",
                extra={
                    "channel": CHANNEL,
                    "external_id": external_id,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            return

        logger.info("channel.sender.sent", extra={"channel": CHANNEL, "external_id": external_id})
