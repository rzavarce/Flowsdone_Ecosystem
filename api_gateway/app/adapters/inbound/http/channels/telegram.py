from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

from .....application.use_cases.route_channel_message import ChannelMessageNotRoutable
from .....core.config import settings

logger = logging.getLogger("channels.telegram")

router = APIRouter(prefix="/webhooks/telegram", tags=["channels:telegram"])

CHANNEL_TYPE = "telegram"


@router.post("/{bot_token}")
async def receive_webhook(
    bot_token: str,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> JSONResponse:
    if not settings.TELEGRAM_WEBHOOK_SECRET or x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning("channels.telegram.invalid_secret")
        return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_secret"})

    update = await request.json()
    route_use_case = request.app.state.route_channel_message_use_case

    message = update.get("message") or {}
    text = message.get("text")
    chat_id = (message.get("chat") or {}).get("id")
    sender_id = (message.get("from") or {}).get("id")

    if text and chat_id is not None and sender_id is not None:
        await _route_event(route_use_case, bot_token, str(chat_id), str(sender_id), text, update)

    return JSONResponse(status_code=200, content={"ok": True})


async def _route_event(
    route_use_case: Any,
    bot_token: str,
    chat_id: str,
    sender_id: str,
    text: str,
    raw_update: Dict[str, Any],
) -> None:
    try:
        await route_use_case.execute(
            channel_type=CHANNEL_TYPE,
            external_id=bot_token,
            external_conversation_key=chat_id,
            sender_id=sender_id,
            payload={"message": text, "raw": raw_update},
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.telegram.not_routable",
            extra={"bot_token": bot_token, "chat_id": chat_id},
        )
    except Exception:
        logger.exception("channels.telegram.routing_failed")
