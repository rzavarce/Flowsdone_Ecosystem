"""Chatwoot Cloud as a pipe to Facebook Messenger and Instagram DM.

The SaaS has one Chatwoot account (the "chatwoot" channel_app) holding
every client's Facebook page / Instagram account as an inbox, and one
Agent Bot assigned to the inboxes Flowsdone answers. Chatwoot owns the
approved Meta app; Flowsdone only receives the bot's webhooks and posts
replies as the bot.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.domain.models.channel_app import ChannelApp
from app.domain.ports.outbound import ChannelAppRepositoryPort

logger = logging.getLogger("channels.chatwoot.api")

PROVIDER = "chatwoot"
DEFAULT_BASE_URL = "https://app.chatwoot.com"

# channel_app credentials / config keys.
API_ACCESS_TOKEN_FIELD = "api_access_token"
WEBHOOK_TOKEN_FIELD = "webhook_token"
BOT_ACCESS_TOKEN_FIELD = "bot_access_token"
ACCOUNT_ID_FIELD = "account_id"
BASE_URL_FIELD = "base_url"
BOT_ID_FIELD = "bot_id"

BOT_NAME = "Flowsdone"


class ChatwootError(Exception):
    """Raised when the Chatwoot app is not configured or its API fails."""


def base_url(app: ChannelApp) -> str:
    """The Chatwoot instance of the app.

    Args:
        app (ChannelApp): The "chatwoot" channel_app.

    Returns:
        str: `config.base_url` without trailing slash, or Chatwoot Cloud.
    """
    return str(app.config.get(BASE_URL_FIELD) or DEFAULT_BASE_URL).rstrip("/")


def callback_url(webhook_token: str) -> str:
    """Our public URL for the Agent Bot's webhooks.

    Args:
        webhook_token (str): The app's generated webhook token.

    Returns:
        str: The bot's outgoing_url.
    """
    return f"{settings.PUBLIC_BASE_URL}/webhooks/chatwoot?token={webhook_token}"


class ChatwootClient:
    """Thin wrapper over the few Chatwoot Application API calls used here."""

    def __init__(self, channel_app_repo: Optional[ChannelAppRepositoryPort]) -> None:
        """Build the client.

        Args:
            channel_app_repo (Optional[ChannelAppRepositoryPort]): Where the
                "chatwoot" app lives; None makes every call fail cleanly.
        """
        self._repo = channel_app_repo

    async def app(self) -> ChannelApp:
        """Load the configured "chatwoot" app.

        Returns:
            ChannelApp: The app, with an account id and an admin token.

        Raises:
            ChatwootError: If it is missing or incomplete.
        """
        app = await self._repo.get_by_provider(PROVIDER) if self._repo else None
        if app is None or not app.credentials.get(API_ACCESS_TOKEN_FIELD) or not app.config.get(ACCOUNT_ID_FIELD):
            raise ChatwootError("the chatwoot channel app is not configured (api_access_token, account_id)")
        return app

    async def ensure_bot(self) -> ChannelApp:
        """Return the app, creating the shared Agent Bot first if needed.

        The bot's id and access token are stored back into the app (they
        survive admin upserts, see UpsertChannelAppUseCase).

        Returns:
            ChannelApp: The app, with `config.bot_id` and the bot token set.

        Raises:
            ChatwootError: If the app is not configured or Chatwoot fails.
        """
        app = await self.app()
        if app.config.get(BOT_ID_FIELD) and app.credentials.get(BOT_ACCESS_TOKEN_FIELD):
            return app

        webhook_token = app.credentials.get(WEBHOOK_TOKEN_FIELD)
        if not webhook_token:
            raise ChatwootError("the chatwoot channel app has no webhook_token")

        bot = await self._request(
            app,
            "POST",
            "agent_bots",
            token=app.credentials[API_ACCESS_TOKEN_FIELD],
            json={
                "name": BOT_NAME,
                "description": "Flowsdone agents answer the conversations of this inbox.",
                "outgoing_url": callback_url(webhook_token),
                "bot_type": 0,
            },
        )
        if not bot.get("id") or not bot.get("access_token"):
            raise ChatwootError("Chatwoot did not return the agent bot id/access_token")

        logger.info("channels.chatwoot.bot_created", extra={"bot_id": bot["id"]})
        return await self._repo.upsert(
            provider=PROVIDER,
            credentials={**app.credentials, BOT_ACCESS_TOKEN_FIELD: bot["access_token"]},
            config={**app.config, BOT_ID_FIELD: bot["id"]},
        )

    async def set_inbox_bot(self, inbox_id: str, bot_id: Optional[int]) -> None:
        """Assign the bot to an inbox, or remove it (`bot_id=None`).

        Args:
            inbox_id (str): Chatwoot inbox id.
            bot_id (Optional[int]): Agent Bot id, None to unassign.

        Raises:
            ChatwootError: If the app is not configured or Chatwoot fails.
        """
        app = await self.app()
        await self._request(
            app,
            "POST",
            f"inboxes/{inbox_id}/set_agent_bot",
            token=app.credentials[API_ACCESS_TOKEN_FIELD],
            json={"agent_bot": bot_id},
        )

    async def send_message(self, conversation_id: str, text: str) -> None:
        """Post an outgoing message to a conversation, as the bot.

        Args:
            conversation_id (str): Chatwoot conversation id.
            text (str): Message body.

        Raises:
            ChatwootError: If the bot is not set up or Chatwoot fails.
        """
        app = await self.app()
        bot_token = app.credentials.get(BOT_ACCESS_TOKEN_FIELD)
        if not bot_token:
            raise ChatwootError("the chatwoot agent bot is not set up yet (connect an inbox first)")
        await self._request(
            app,
            "POST",
            f"conversations/{conversation_id}/messages",
            token=bot_token,
            json={"content": text, "message_type": "outgoing", "private": False},
        )

    async def _request(self, app: ChannelApp, method: str, path: str, *, token: str, json: Dict[str, Any]) -> Dict[str, Any]:
        """Call an account-scoped Chatwoot API endpoint.

        Args:
            app (ChannelApp): The configured app (instance and account).
            method (str): HTTP method.
            path (str): Path below /api/v1/accounts/{account_id}/.
            token (str): The api_access_token to authenticate with.
            json (Dict[str, Any]): Request body.

        Returns:
            Dict[str, Any]: The JSON response ({} if it has none).

        Raises:
            ChatwootError: If the request fails or Chatwoot answers with an error.
        """
        url = f"{base_url(app)}/api/v1/accounts/{app.config[ACCOUNT_ID_FIELD]}/{path}"
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.request(method, url, headers={"api_access_token": token}, json=json)
            except httpx.HTTPError as exc:
                raise ChatwootError(f"could not reach Chatwoot: {exc}") from exc

        if response.status_code >= 400:
            logger.error(
                "channels.chatwoot.api_error",
                extra={"path": path, "status_code": response.status_code, "response_text": response.text},
            )
            raise ChatwootError(f"Chatwoot rejected {method} {path}: {response.status_code}")

        is_json = response.headers.get("content-type", "").startswith("application/json")
        return response.json() if is_json else {}
