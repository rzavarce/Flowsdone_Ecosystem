from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ....core.config import settings
from ....domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.whatsapp_evolution.sender")


class WhatsAppEvolutionSender(ChannelSenderPort):
    """
    external_id = instance de Evolution API (mismo valor usado para el
    routing de webhooks entrantes). El apikey es el shared secret de
    nuestra propia instancia de Evolution (settings.EVOLUTION_API_KEY),
    no algo por-conexión.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
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
