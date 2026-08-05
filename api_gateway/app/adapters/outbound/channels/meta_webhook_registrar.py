"""Meta Graph API page subscription (Facebook Messenger + Instagram DM).

Meta's webhook *callback URL* and *app secret* are configured once at
the app level (`channel_apps.meta`, set up via the Meta dashboard or
`/internal/admin/channel-apps/meta`) — that part is out of scope here.
What's still a manual, per-connection curl call today is telling Meta
"this specific page should actually send events to that app": `POST
/{page_id}/subscribed_apps`. This registrar automates that call, the
real per-connection equivalent of Telegram's `setWebhook`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from ....core.config import settings

logger = logging.getLogger("channels.meta.webhook_registrar")


class MetaWebhookRegistrationError(Exception):
    """Raised when the Meta Graph API rejects or fails a subscribed_apps call."""


class MetaWebhookRegistrar:
    """Subscribes/unsubscribes a Facebook Page (or its linked Instagram
    Business Account) to the SaaS's shared Meta app.

    Unlike Telegram, Meta doesn't need a secret we generate — inbound
    webhooks are verified with the shared `channel_apps.meta.app_secret`
    (see channels/meta_common.py), so `secret_field` is None. What this
    needs from `credentials` is `page_access_token`, the same value
    FacebookSender/InstagramSender already use to send messages (see
    meta_sender.py) — supplied by the admin, not generated here.

    Facebook and Instagram messaging both subscribe through the same
    Graph API page-level endpoint, only the requested
    `subscribed_fields` differ; one parametrized class covers both
    (see WebhookRegistrarFactory) instead of two near-identical ones.
    """

    secret_field = None

    def __init__(self, *, channel: str, subscribed_fields: str) -> None:
        """Build the registrar.

        Args:
            channel (str): Logical channel name, used only for logging
                ("facebook" or "instagram").
            subscribed_fields (str): Comma-separated Graph API webhook
                fields to subscribe the page to (e.g. "messages,
                messaging_postbacks").
        """
        self._channel = channel
        self._subscribed_fields = subscribed_fields

    async def register(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Subscribe a page to the shared Meta app's webhook.

        Args:
            external_id (str): Facebook page id (or, for Instagram, the
                id of the page linked to the IG business account).
            credentials (Dict[str, Any]): Must contain
                "page_access_token".

        Raises:
            MetaWebhookRegistrationError: If `page_access_token` is
                missing, or the Graph API call fails/rejects it.
        """
        page_access_token = self._require_page_access_token(credentials)

        await self._call_subscribed_apps(
            "POST",
            external_id,
            page_access_token,
            params={"subscribed_fields": self._subscribed_fields},
        )

        logger.info(
            "channel.webhook_registrar.registered",
            extra={"channel": self._channel, "external_id": external_id},
        )

    async def deregister(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Unsubscribe a page from the shared Meta app's webhook.

        Args:
            external_id (str): Facebook page id (or linked page id for
                Instagram).
            credentials (Dict[str, Any]): Must contain
                "page_access_token".

        Raises:
            MetaWebhookRegistrationError: If `page_access_token` is
                missing, or the Graph API call fails/rejects it.
        """
        page_access_token = self._require_page_access_token(credentials)

        await self._call_subscribed_apps("DELETE", external_id, page_access_token)

        logger.info(
            "channel.webhook_registrar.deregistered",
            extra={"channel": self._channel, "external_id": external_id},
        )

    def _require_page_access_token(self, credentials: Dict[str, Any]) -> str:
        """Extract `page_access_token`, raising if it's missing.

        Args:
            credentials (Dict[str, Any]): The channel_connection's credentials.

        Returns:
            str: The page access token.

        Raises:
            MetaWebhookRegistrationError: If `page_access_token` is
                absent or empty.
        """
        page_access_token = credentials.get("page_access_token")
        if not page_access_token:
            raise MetaWebhookRegistrationError(
                "credentials.page_access_token is required to (de)register a "
                f"{self._channel} webhook subscription"
            )
        return page_access_token

    async def _call_subscribed_apps(
        self,
        http_method: str,
        page_id: str,
        page_access_token: str,
        *,
        params: Dict[str, str] | None = None,
    ) -> None:
        """Call `/{page_id}/subscribed_apps` and raise unless Meta confirms it.

        Args:
            http_method (str): "POST" to subscribe, "DELETE" to unsubscribe.
            page_id (str): Facebook page id.
            page_access_token (str): The page's access token.
            params (Dict[str, str] | None): Extra query params (e.g.
                `subscribed_fields` on subscribe).

        Raises:
            MetaWebhookRegistrationError: If the request fails or Meta
                does not confirm with `"success": true`.
        """
        url = (
            f"{settings.META_GRAPH_API_BASE_URL}/{settings.META_GRAPH_API_VERSION}"
            f"/{page_id}/subscribed_apps"
        )
        query = {"access_token": page_access_token, **(params or {})}

        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.request(http_method, url, params=query)
            except httpx.HTTPError as exc:
                logger.error(
                    "channel.webhook_registrar.request_failed",
                    extra={"channel": self._channel, "http_method": http_method},
                )
                raise MetaWebhookRegistrationError(
                    f"could not reach the Meta Graph API ({http_method}): {exc}"
                ) from exc

        body = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )

        if response.status_code >= 400 or not body.get("success", False):
            logger.error(
                "channel.webhook_registrar.rejected",
                extra={
                    "channel": self._channel,
                    "http_method": http_method,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise MetaWebhookRegistrationError(
                f"Meta rejected {http_method} /subscribed_apps: {response.text}"
            )
