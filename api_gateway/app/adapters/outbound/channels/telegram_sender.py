"""Telegram outbound channel sender."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.core.config import settings
from app.domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.telegram.sender")


class TelegramSender(ChannelSenderPort):
    """Sends messages via the Telegram Bot API.

    `external_id` is the bot token (the same value used for inbound
    webhook routing).
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Send a text message to a Telegram chat.

        Args:
            external_id (str): Telegram bot token.
            recipient_id (str): Telegram chat id.
            text (str): Message body to send.
            credentials (Dict[str, Any]): Unused for Telegram; kept for
                interface consistency with ChannelSenderPort.
        """
        url = f"{settings.TELEGRAM_API_BASE_URL}/bot{external_id}/sendMessage"

        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                url,
                json={"chat_id": recipient_id, "text": text},
            )

        if response.status_code >= 400:
            logger.error(
                "channel.sender.failed",
                extra={
                    "channel": "telegram",
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            return

        logger.info("channel.sender.sent", extra={"channel": "telegram"})
