"""TikTok outbound channel sender (stub)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from ....domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.tiktok.sender")


class TikTokSender(ChannelSenderPort):
    """Stub sender for TikTok messages.

    TikTok does not offer a stable public "send message" API for
    third-party apps outside of Business Messaging (which requires
    prior approval). Does not raise and does not pretend to succeed.
    """

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Log that sending is not implemented for this channel.

        Args:
            external_id (str): TikTok open_id.
            recipient_id (str): Id of the intended recipient.
            text (str): Message body that would have been sent.
            credentials (Dict[str, Any]): Channel credentials (unused).
        """
        logger.warning(
            "channel.sender.not_implemented",
            extra={
                "channel": "tiktok",
                "external_id": external_id,
                "recipient_id": recipient_id,
            },
        )
