"""Shared Graph API message-sending logic for Facebook and Instagram."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ....core.config import settings

logger = logging.getLogger("channels.meta.sender")


async def send_meta_message(
    *,
    channel: str,
    external_id: str,
    recipient_id: str,
    text: str,
    credentials: Dict[str, Any],
) -> None:
    """Send a text message via the Meta Graph API.

    Shared by Facebook Messenger and Instagram, which use the same
    messaging endpoint and payload shape.

    Args:
        channel (str): Logical channel name, used only for logging
            ("facebook" or "instagram").
        external_id (str): Facebook page id or Instagram business
            account id.
        recipient_id (str): Id of the message recipient (psid).
        text (str): Message body to send.
        credentials (Dict[str, Any]): Channel credentials; must contain
            "page_access_token".
    """
    page_access_token = credentials.get("page_access_token")

    if not page_access_token:
        logger.error(
            "channel.sender.missing_credentials",
            extra={"channel": channel, "external_id": external_id},
        )
        return

    url = (
        f"{settings.META_GRAPH_API_BASE_URL}/{settings.META_GRAPH_API_VERSION}"
        f"/{external_id}/messages"
    )

    async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            params={"access_token": page_access_token},
            json={
                "recipient": {"id": recipient_id},
                "message": {"text": text},
            },
        )

    if response.status_code >= 400:
        logger.error(
            "channel.sender.failed",
            extra={
                "channel": channel,
                "external_id": external_id,
                "status_code": response.status_code,
                "response_text": response.text,
            },
        )
        return

    logger.info(
        "channel.sender.sent",
        extra={"channel": channel, "external_id": external_id},
    )
