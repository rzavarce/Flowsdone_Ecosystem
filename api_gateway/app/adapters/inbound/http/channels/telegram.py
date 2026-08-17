"""Telegram inbound webhook."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

from .....application.services.switchboard import ChannelMessageNotRoutable

logger = logging.getLogger("channels.telegram")

router = APIRouter(prefix="/webhooks/telegram", tags=["channels:telegram"])

CHANNEL_TYPE = "telegram"


@router.post("/{bot_token}")
async def receive_webhook(
    bot_token: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    """Receive a Telegram Bot API update and route the message.

    Unlike Meta/X/TikTok (a single shared app), each client has their
    own Telegram bot with its own secret_token, stored alongside the
    rest of its credentials in channel_connections rather than in
    channel_apps.

    Args:
        bot_token (str): Telegram bot token, taken from the webhook
            path and used as the channel connection's external_id.
        request (Request): The incoming FastAPI request.
        x_telegram_bot_api_secret_token (str | None): Secret token
            Telegram sends in this header, configured via setWebhook.

    Returns:
        JSONResponse: Acknowledges the update to Telegram.
    """
    channel_connection_repo = request.app.state.channel_connection_repo
    resolution = await channel_connection_repo.get_by_channel_and_external_id(
        CHANNEL_TYPE, bot_token
    )
    expected_secret = resolution.credentials.get("telegram_webhook_secret") if resolution else None

    if not expected_secret or x_telegram_bot_api_secret_token != expected_secret:
        logger.warning("channels.telegram.invalid_secret")
        return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_secret"})

    update = await request.json()
    switchboard = request.app.state.switchboard

    message = update.get("message") or {}
    text = message.get("text")
    chat_id = (message.get("chat") or {}).get("id")
    sender_id = (message.get("from") or {}).get("id")

    if text and chat_id is not None and sender_id is not None:
        await _route_event(switchboard, bot_token, str(chat_id), str(sender_id), text, update)

    return JSONResponse(status_code=200, content={"ok": True})


async def _route_event(
    switchboard: Any,
    bot_token: str,
    chat_id: str,
    sender_id: str,
    text: str,
    raw_update: Dict[str, Any],
) -> None:
    """Route a single Telegram message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        bot_token (str): Telegram bot token the update was sent to.
        chat_id (str): Telegram chat id.
        sender_id (str): Id of the sender.
        text (str): Message text.
        raw_update (Dict[str, Any]): The raw Telegram update, kept in
            the payload for debugging.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=bot_token,
            external_conversation_key=chat_id,
            sender_id=sender_id,
            message_text=text,
            raw_payload=raw_update,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.telegram.not_routable",
            extra={"bot_token": bot_token, "chat_id": chat_id},
        )
    except Exception:
        logger.exception("channels.telegram.routing_failed")
