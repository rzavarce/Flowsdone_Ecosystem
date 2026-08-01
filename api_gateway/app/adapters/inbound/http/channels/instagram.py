from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, PlainTextResponse

from .....application.use_cases.route_channel_message import ChannelMessageNotRoutable
from .....core.config import settings
from .meta_common import handle_verification_challenge, verify_meta_signature

logger = logging.getLogger("channels.instagram")

router = APIRouter(prefix="/webhooks/instagram", tags=["channels:instagram"])

CHANNEL_TYPE = "instagram"


@router.get("")
async def verify_webhook(request: Request) -> PlainTextResponse:
    params = request.query_params
    return handle_verification_challenge(
        mode=params.get("hub.mode"),
        verify_token=params.get("hub.verify_token"),
        challenge=params.get("hub.challenge"),
        expected_token=settings.META_WEBHOOK_VERIFY_TOKEN,
    )


@router.post("")
async def receive_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_meta_signature(raw_body, signature, settings.META_APP_SECRET or ""):
        logger.warning("channels.instagram.invalid_signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    body = await request.json()
    route_use_case = request.app.state.route_channel_message_use_case

    for entry in body.get("entry", []):
        ig_account_id = entry.get("id")
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            text = message.get("text")
            sender_id = (event.get("sender") or {}).get("id")

            if not ig_account_id or not sender_id or not text:
                continue

            await _route_event(route_use_case, ig_account_id, sender_id, text, event)

    return JSONResponse(status_code=200, content={"status": "EVENT_RECEIVED"})


async def _route_event(
    route_use_case: Any,
    ig_account_id: str,
    sender_id: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    try:
        await route_use_case.execute(
            channel_type=CHANNEL_TYPE,
            external_id=ig_account_id,
            external_conversation_key=sender_id,
            sender_id=sender_id,
            payload={"message": text, "raw": raw_event},
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.instagram.not_routable",
            extra={"ig_account_id": ig_account_id, "sender_id": sender_id},
        )
    except Exception:
        logger.exception("channels.instagram.routing_failed")
