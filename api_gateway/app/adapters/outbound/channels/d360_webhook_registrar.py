"""360dialog webhook registration (WhatsApp Cloud API via 360dialog)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.adapters.outbound.channels.d360_api import (
    API_KEY_FIELD,
    WEBHOOK_SECRET_FIELD,
    WEBHOOK_SECRET_HEADER,
    callback_url,
    webhook_config_url,
)
from app.core.config import settings

logger = logging.getLogger("channels.whatsapp_360dialog.webhook_registrar")

CHANNEL = "whatsapp_360dialog"


class D360WebhookRegistrationError(Exception):
    """Raised when 360dialog rejects or fails a webhook configuration call."""


class D360WebhookRegistrar:
    """Points a 360dialog number's webhook at our gateway.

    360dialog does not sign its webhooks, so the gateway generates a
    secret per connection (`secret_field`) and asks 360dialog to send it
    back in a custom header on every call; the inbound endpoint rejects
    any call without it.
    """

    secret_field = WEBHOOK_SECRET_FIELD

    async def register(
        self, *, external_id: str, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set the number's webhook URL and secret header.

        Args:
            external_id (str): The connection's business number (digits),
                part of our callback URL.
            credentials (Dict[str, Any]): Must contain "api_key" and the
                generated `secret_field`.
            config (Optional[Dict[str, Any]]): {"sandbox": true} targets
                the sandbox host.

        Raises:
            D360WebhookRegistrationError: If the API key or secret is
                missing, or 360dialog fails/rejects the call.
        """
        api_key = credentials.get(API_KEY_FIELD)
        secret = credentials.get(self.secret_field)
        if not api_key or not secret:
            raise D360WebhookRegistrationError("a 360dialog connection needs an api_key")

        url = callback_url(external_id)
        await self._configure(
            config or {},
            api_key,
            {"url": url, "headers": {WEBHOOK_SECRET_HEADER: secret}},
        )
        logger.info(
            "channel.webhook_registrar.registered",
            extra={"channel": CHANNEL, "callback_url": url},
        )

    async def deregister(
        self, *, external_id: str, credentials: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Nothing to undo on 360dialog's side.

        360dialog has no "delete webhook" call. Once the connection is
        gone, our endpoint acknowledges and drops whatever still arrives
        for that number, and the next registration overwrites the URL.

        Args:
            external_id (str): The connection's business number.
            credentials (Dict[str, Any]): Unused.
            config (Optional[Dict[str, Any]]): Unused.
        """
        logger.info(
            "channel.webhook_registrar.deregister_noop",
            extra={"channel": CHANNEL, "external_id": external_id},
        )

    async def _configure(self, config: Dict[str, Any], api_key: str, body: Dict[str, Any]) -> None:
        """POST a webhook configuration to 360dialog.

        Args:
            config (Dict[str, Any]): Picks the sandbox or production host.
            api_key (str): The number's D360-API-KEY.
            body (Dict[str, Any]): The configuration to send.

        Raises:
            D360WebhookRegistrationError: If the request fails or
                360dialog answers with an error status.
        """
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(
                    webhook_config_url(config),
                    headers={"D360-API-KEY": api_key},
                    json=body,
                )
            except httpx.HTTPError as exc:
                logger.error("channel.webhook_registrar.request_failed", extra={"channel": CHANNEL})
                raise D360WebhookRegistrationError(f"could not reach 360dialog: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "channel.webhook_registrar.rejected",
                extra={
                    "channel": CHANNEL,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise D360WebhookRegistrationError(f"360dialog rejected the webhook: {response.text}")
