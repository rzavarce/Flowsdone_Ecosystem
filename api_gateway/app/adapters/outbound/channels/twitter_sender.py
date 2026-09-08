"""X (Twitter) outbound channel sender (stub)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.domain.ports.outbound import ChannelSenderPort

logger = logging.getLogger("channels.twitter.sender")


class TwitterSender(ChannelSenderPort):
    """Stub sender for X (Twitter) Direct Messages.

    Sending real Direct Messages on X requires their paid API tier and
    OAuth1.0a request signing (consumer_key/consumer_secret plus a
    per-connection access_token/access_token_secret), none of which is
    implemented yet. Does not raise and does not pretend to succeed.
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
            external_id (str): X account id.
            recipient_id (str): Id of the intended recipient.
            text (str): Message body that would have been sent.
            credentials (Dict[str, Any]): Channel credentials (unused).
        """
        logger.warning(
            "channel.sender.not_implemented",
            extra={
                "channel": "twitter",
                "external_id": external_id,
                "recipient_id": recipient_id,
            },
        )
