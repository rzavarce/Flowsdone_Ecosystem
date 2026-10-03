"""Chatwoot Agent Bot inbound webhook (Facebook / Instagram via Chatwoot)."""

from __future__ import annotations

import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.adapters.outbound.channels.chatwoot_api import ACCOUNT_ID_FIELD, PROVIDER, WEBHOOK_TOKEN_FIELD
from app.application.services.switchboard import ChannelMessageNotRoutable
from app.domain.models.conversation_contact import SenderProfile

logger = logging.getLogger("channels.chatwoot")

router = APIRouter(prefix="/webhooks/chatwoot", tags=["channels:chatwoot"])

CHANNEL_TYPE = "chatwoot"


def _is_incoming(message_type: Any) -> bool:
    """Whether a Chatwoot message was written by the contact.

    Args:
        message_type (Any): The event's `message_type` ("incoming", or
            0 in older payloads).

    Returns:
        bool: True for messages from the contact; False for the bot's or
        an agent's own messages, activity and template messages.
    """
    return message_type in ("incoming", 0)


def _sender_profile(sender: Dict[str, Any]) -> SenderProfile:
    """What a Chatwoot event says about the contact.

    Args:
        sender (Dict[str, Any]): The event's "sender" object.

    Returns:
        SenderProfile: Name and, when Chatwoot knows it, phone.
    """
    name = (sender.get("name") or "").strip()
    return SenderProfile(name=name or None, phone=sender.get("phone_number") or None)


@router.post("")
async def receive_webhook(request: Request, token: Optional[str] = None) -> JSONResponse:
    """Receive a Chatwoot Agent Bot event and route the contact's message.

    Args:
        request (Request): The incoming FastAPI request.
        token (Optional[str]): The `token` query parameter of the bot's
            outgoing_url; must match the app's webhook_token.

    Returns:
        JSONResponse: 200 once handled (including events that are
        ignored), 401 if the token is wrong.
    """
    app = await request.app.state.channel_app_repo.get_by_provider(PROVIDER)
    expected = (app.credentials.get(WEBHOOK_TOKEN_FIELD) if app else None) or ""
    if not expected or not hmac.compare_digest((token or "").encode(), expected.encode()):
        logger.warning("channels.chatwoot.invalid_token")
        return JSONResponse(status_code=401, content={"status": "invalid_token"})

    event = await request.json()
    if event.get("event") != "message_created" or not _is_incoming(event.get("message_type")) or event.get("private"):
        return JSONResponse(status_code=200, content={"status": "ignored"})

    account_id = (event.get("account") or {}).get("id")
    if str(account_id) != str(app.config.get(ACCOUNT_ID_FIELD)):
        logger.warning("channels.chatwoot.foreign_account", extra={"account_id": account_id})
        return JSONResponse(status_code=200, content={"status": "ignored"})

    conversation = event.get("conversation") or {}
    conversation_id = conversation.get("id")
    inbox_id = (event.get("inbox") or {}).get("id") or conversation.get("inbox_id")
    text = (event.get("content") or "").strip()

    if conversation_id and inbox_id and text:
        await _route_event(
            request.app.state.switchboard,
            str(inbox_id),
            str(conversation_id),
            text,
            event,
            _sender_profile(event.get("sender") or {}),
        )

    return JSONResponse(status_code=200, content={"status": "ok"})


async def _route_event(
    switchboard: Any,
    inbox_id: str,
    conversation_id: str,
    text: str,
    raw_event: Dict[str, Any],
    sender_profile: Optional[SenderProfile] = None,
) -> None:
    """Route a single Chatwoot message to its currently assigned app.

    Args:
        switchboard (Any): The Switchboard instance.
        inbox_id (str): Chatwoot inbox id (the connection's external_id).
        conversation_id (str): Chatwoot conversation id (conversation key
            and the recipient of the replies).
        text (str): Message text.
        raw_event (Dict[str, Any]): The raw Chatwoot event, kept in the
            payload for debugging (its conversation.channel says whether
            it came from Facebook or Instagram).
        sender_profile (Optional[SenderProfile]): Name and phone of the
            contact, for their contact card.
    """
    sender_id = str(((raw_event.get("sender") or {}).get("id")) or conversation_id)
    try:
        await switchboard.handle_inbound_turn(
            channel_type=CHANNEL_TYPE,
            external_id=inbox_id,
            external_conversation_key=conversation_id,
            sender_id=sender_id,
            message_text=text,
            raw_payload=raw_event,
            sender_profile=sender_profile,
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.chatwoot.not_routable",
            extra={"inbox_id": inbox_id, "conversation_id": conversation_id},
        )
    except Exception:
        logger.exception("channels.chatwoot.routing_failed")
