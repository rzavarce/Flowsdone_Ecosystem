from __future__ import annotations

from typing import Any, Dict

from ....domain.ports.outbound import ChannelSenderPort
from .meta_sender import send_meta_message


class InstagramSender(ChannelSenderPort):
    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        await send_meta_message(
            channel="instagram",
            external_id=external_id,
            recipient_id=recipient_id,
            text=text,
            credentials=credentials,
        )
