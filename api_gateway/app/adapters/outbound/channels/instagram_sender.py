"""Instagram DM outbound channel sender."""

from __future__ import annotations

from typing import Any, Dict

from ....domain.ports.outbound import ChannelSenderPort
from .meta_sender import send_meta_message


class InstagramSender(ChannelSenderPort):
    """Sends messages to Instagram DMs via the Meta Graph API."""

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Send a text message to an Instagram DM recipient.

        Args:
            external_id (str): Instagram business account id.
            recipient_id (str): Id of the message recipient.
            text (str): Message body to send.
            credentials (Dict[str, Any]): Channel credentials; must
                contain "page_access_token".
        """
        await send_meta_message(
            channel="instagram",
            external_id=external_id,
            recipient_id=recipient_id,
            text=text,
            credentials=credentials,
        )
