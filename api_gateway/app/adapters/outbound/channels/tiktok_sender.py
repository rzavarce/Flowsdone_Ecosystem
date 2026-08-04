from __future__ import annotations

import logging
from typing import Any, Dict

from ....domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.tiktok.sender")


class TikTokSender(ChannelSenderPort):
    """
    Stub: TikTok no ofrece una API pública estable de "enviar mensaje"
    para apps de terceros fuera de Business Messaging (requiere
    aprobación previa). No lanza excepción ni finge éxito.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        logger.warning(
            "channel.sender.not_implemented",
            extra={
                "channel": "tiktok",
                "external_id": external_id,
                "recipient_id": recipient_id,
            },
        )
