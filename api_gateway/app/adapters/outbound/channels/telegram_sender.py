from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ....core.config import settings
from ....domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.telegram.sender")


class TelegramSender(ChannelSenderPort):
    """external_id = bot_token (mismo valor usado para el routing entrante)."""

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
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
