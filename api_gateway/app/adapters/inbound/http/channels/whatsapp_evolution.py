"""WhatsApp (Evolution API) inbound webhook."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, Request
from starlette.responses import JSONResponse

from .....application.services.switchboard import ChannelMessageNotRoutable
from .....core.config import settings

logger = logging.getLogger("channels.whatsapp_evolution")

router = APIRouter(prefix="/webhooks/whatsapp", tags=["channels:whatsapp"])

CHANNEL_TYPE = "whatsapp_evolution"


def _extract_text(message: Dict[str, Any]) -> Optional[str]:
    """Extract the text body from an Evolution API message object.

    Args:
        message (Dict[str, Any]): The "message" object from an
            Evolution API event.

    Returns:
        Optional[str]: The message text, or None if it has no
        recognized text field.
    """
    if "conversation" in message:
        return message["conversation"]

    extended = message.get("extendedTextMessage") or {}
    if "text" in extended:
        return extended["text"]

    return None


@router.post("")
async def receive_webhook(
    request: Request,
    apikey: Optional[str] = Header(default=None),
) -> JSONResponse:
    """Receive an Evolution API webhook event and route the message.

    Args:
        request (Request): The incoming FastAPI request.
        apikey (Optional[str]): Evolution API shared secret, validated
            against settings.EVOLUTION_API_KEY.

    Returns:
        JSONResponse: Acknowledges the event.
    """
    if not settings.EVOLUTION_API_KEY or apikey != settings.EVOLUTION_API_KEY:
        logger.warning("channels.whatsapp_evolution.invalid_api_key")
        return JSONResponse(status_code=401, content={"status": "invalid_api_key"})

    body = await request.json()

    if body.get("event") != "messages.upsert":
        return JSONResponse(status_code=200, content={"status": "ignored"})

    instance = body.get("instance")
    data = body.get("data") or {}
    key = data.get("key") or {}

    if key.get("fromMe"):
        return JSONResponse(status_code=200, content={"status": "ignored"})

    remote_jid = key.get("remoteJid")
    text = _extract_text(data.get("message") or {})

    if instance and remote_jid and text:
        switchboard = request.app.state.switchboard
        await _route_event(switchboard, instance, remote_jid, text, body)

    return JSONResponse(status_code=200, content={"status": "ok"})


async def _route_event(
    switchboard: Any,
    instance: str,
    remote_jid: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    """Route a single WhatsApp message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        instance (str): Evolution API instance name the message
            arrived on.
        remote_jid (str): WhatsApp id of the sender.
        text (str): Message text.
        raw_event (Dict[str, Any]): The raw Evolution API event, kept
            in the payload for debugging.
    """
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=instance,
            external_conversation_key=remote_jid,
            sender_id=remote_jid,
            message_text=text,
            raw_payload=raw_event,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.whatsapp_evolution.not_routable",
            extra={"instance": instance, "remote_jid": remote_jid},
        )
    except Exception:
        logger.exception("channels.whatsapp_evolution.routing_failed")
