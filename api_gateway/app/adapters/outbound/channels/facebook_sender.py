"""Facebook Messenger outbound channel sender."""

from __future__ import annotations

from typing import Any, Dict

from api_gateway.app.domain.ports.outbound import ChannelSenderPort
from api_gateway.app.adapters.outbound.channels.meta_sender import send_meta_message


class FacebookSender(ChannelSenderPort):
    """Sends messages to Facebook Messenger via the Meta Graph API."""

    async def send(
        self,
        *,
        external_id: str,
        recipient_id: str,
        text: str,
        credentials: Dict[str, Any],
    ) -> None:
        """Send a text message to a Facebook Messenger recipient.

        Args:
            external_id (str): Facebook page id.
            recipient_id (str): Id of the message recipient (psid).
            text (str): Message body to send.
            credentials (Dict[str, Any]): Channel credentials; must
                contain "page_access_token".
        """
        await send_meta_message(
            channel="facebook",
            external_id=external_id,
            recipient_id=recipient_id,
            text=text,
            credentials=credentials,
        )
