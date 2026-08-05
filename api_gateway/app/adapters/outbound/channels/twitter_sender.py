from __future__ import annotations

import logging
from typing import Any, Dict

from ....domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.twitter.sender")


class TwitterSender(ChannelSenderPort):
    """
    Stub: el envío real de Direct Messages en X requiere su tier de pago
    de API y firma OAuth1.0a (consumer_key/consumer_secret +
    access_token/access_token_secret por conexión), que no están
    implementados todavía. No lanza excepción ni finge éxito.
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
                "channel": "twitter",
                "external_id": external_id,
                "recipient_id": recipient_id,
            },
        )
