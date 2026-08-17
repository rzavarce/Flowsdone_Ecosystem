"""Telegram webhook auto-registration (Bot API `setWebhook`)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from api_gateway.app.core.config import settings

logger = logging.getLogger("channels.telegram.webhook_registrar")


class TelegramWebhookRegistrationError(Exception):
    """Raised when Telegram's Bot API rejects or fails a setWebhook call."""


class TelegramWebhookRegistrar:
    """Calls Telegram's `setWebhook` so connecting a bot never requires
    an admin to run curl by hand.

    `external_id` on a Telegram channel_connection is the bot token
    (see channels/telegram.py); this reuses it both to address the Bot
    API and to build the webhook URL that Telegram must call back.
    """

    secret_field = "telegram_webhook_secret"

    async def register(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Register the gateway's Telegram webhook for one bot.

        Args:
            external_id (str): The bot token.
            credentials (Dict[str, Any]): Must contain
                `telegram_webhook_secret` — the value Telegram must
                echo back via `X-Telegram-Bot-Api-Secret-Token` on
                every update.

        Raises:
            TelegramWebhookRegistrationError: If the Bot API call
                fails or does not confirm the webhook was set.
        """
        bot_token = external_id
        callback_url = f"{settings.PUBLIC_BASE_URL}/webhooks/telegram/{bot_token}"

        await self._call_bot_api(
            bot_token,
            "setWebhook",
            data={"url": callback_url, "secret_token": credentials[self.secret_field]},
        )

        logger.info(
            "channel.webhook_registrar.registered",
            extra={"channel": "telegram", "callback_url": callback_url},
        )

    async def deregister(self, *, external_id: str, credentials: Dict[str, Any]) -> None:
        """Remove the gateway's Telegram webhook for one bot.

        Args:
            external_id (str): The bot token.
            credentials (Dict[str, Any]): Unused — Telegram's
                deleteWebhook only needs the bot token. Kept for
                interface consistency with WebhookRegistrarPort.

        Raises:
            TelegramWebhookRegistrationError: If the Bot API call
                fails or does not confirm the webhook was removed.
        """
        bot_token = external_id
        await self._call_bot_api(bot_token, "deleteWebhook", data={})

        logger.info("channel.webhook_registrar.deregistered", extra={"channel": "telegram"})

    async def _call_bot_api(self, bot_token: str, method: str, *, data: dict) -> None:
        """Call a Telegram Bot API method and raise unless it confirms `ok`.

        Args:
            bot_token (str): The bot token, used to address the API.
            method (str): Bot API method name (e.g. "setWebhook").
            data (dict): Form data to send with the request.

        Raises:
            TelegramWebhookRegistrationError: If the request fails or
                Telegram responds without `"ok": true`.
        """
        url = f"{settings.TELEGRAM_API_BASE_URL}/bot{bot_token}/{method}"

        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(url, data=data)
            except httpx.HTTPError as exc:
                logger.error(
                    "channel.webhook_registrar.request_failed",
                    extra={"channel": "telegram", "method": method},
                )
                raise TelegramWebhookRegistrationError(
                    f"could not reach Telegram Bot API ({method}): {exc}"
                ) from exc

        body = (
            response.json()
            if response.headers.get("content-type", "").startswith("application/json")
            else {}
        )

        if response.status_code >= 400 or not body.get("ok", False):
            logger.error(
                "channel.webhook_registrar.rejected",
                extra={
                    "channel": "telegram",
                    "method": method,
                    "status_code": response.status_code,
                    "response_text": response.text,
                },
            )
            raise TelegramWebhookRegistrationError(
                f"Telegram rejected {method}: {response.text}"
            )
