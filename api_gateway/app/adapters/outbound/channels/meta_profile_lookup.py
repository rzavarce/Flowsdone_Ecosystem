"""SenderProfileLookupPort for Facebook Messenger and Instagram (Graph API).

Their webhooks only carry the sender's page-scoped id, so the gateway asks
the Graph API who it is, with the connection's page access token:

- Messenger (User Profile API): `GET /{psid}?fields=first_name,last_name`.
- Instagram: `GET /{igsid}?fields=name,username`.

Called once, when a contact writes for the first time; a failure (missing
permission, expired token) just leaves the card without a name.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.domain.models.conversation_contact import SenderProfile
from app.domain.ports.outbound import SenderProfileLookupPort

logger = logging.getLogger("channels.meta.profile")

_FIELDS = {"facebook": "first_name,last_name", "instagram": "name,username"}


class MetaSenderProfileLookup(SenderProfileLookupPort):
    """Looks up Messenger and Instagram senders in the Graph API."""

    async def lookup(
        self, *, channel_type: str, sender_id: str, credentials: Dict[str, Any]
    ) -> Optional[SenderProfile]:
        """The sender's name (and Instagram @user), best-effort.

        Args:
            channel_type (str): "facebook" or "instagram"; others get None.
            sender_id (str): PSID / IGSID.
            credentials (Dict[str, Any]): Must hold "page_access_token".

        Returns:
            Optional[SenderProfile]: The profile, or None if the channel has
            no lookup or it failed.
        """
        fields = _FIELDS.get(channel_type)
        token = credentials.get("page_access_token")
        if fields is None or not token:
            return None
        url = f"{settings.META_GRAPH_API_BASE_URL}/{settings.META_GRAPH_API_VERSION}/{sender_id}"
        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(url, params={"fields": fields, "access_token": token})
            if response.status_code >= 400:
                logger.warning(
                    "channels.meta.profile.failed",
                    extra={"channel": channel_type, "status_code": response.status_code, "response_text": response.text[:300]},
                )
                return None
            data = response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("channels.meta.profile.failed", extra={"channel": channel_type}, exc_info=True)
            return None
        if channel_type == "facebook":
            name = " ".join(p for p in (data.get("first_name"), data.get("last_name")) if p)
            return SenderProfile(name=name or None)
        username = data.get("username")
        return SenderProfile(name=data.get("name") or None, username=f"@{username}" if username else None)
