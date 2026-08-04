from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from .....application.use_cases.route_channel_message import ChannelMessageNotRoutable

logger = logging.getLogger("channels.twitter")

router = APIRouter(prefix="/webhooks/twitter", tags=["channels:twitter"])

CHANNEL_TYPE = "twitter"
APP_PROVIDER = "twitter"


def _hmac_sha256_base64(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@router.get("")
async def crc_challenge(request: Request) -> JSONResponse:
    """
    X/Twitter Account Activity API: valida la suscripción del webhook
    respondiendo un HMAC-SHA256 del crc_token, firmado con el consumer secret.
    """
    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    consumer_secret = channel_app.credentials.get("consumer_secret") if channel_app else None

    crc_token = request.query_params.get("crc_token")
    if not crc_token or not consumer_secret:
        raise HTTPException(status_code=400, detail="missing crc_token or consumer secret")

    response_token = "sha256=" + _hmac_sha256_base64(consumer_secret, crc_token)
    return JSONResponse(status_code=200, content={"response_token": response_token})


@router.post("")
async def receive_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    signature = request.headers.get("X-Twitter-Webhooks-Signature")

    channel_app = await request.app.state.channel_app_repo.get_by_provider(APP_PROVIDER)
    consumer_secret = channel_app.credentials.get("consumer_secret") if channel_app else None

    if not _verify_signature(raw_body, signature, consumer_secret):
        logger.warning("channels.twitter.invalid_signature")
        return JSONResponse(status_code=401, content={"status": "invalid_signature"})

    body = await request.json()
    route_use_case = request.app.state.route_channel_message_use_case

    account_id = body.get("for_user_id")

    for event in body.get("direct_message_events", []):
        message_create = event.get("message_create") or {}
        sender_id = message_create.get("sender_id")
        text = (message_create.get("message_data") or {}).get("text")

        if not account_id or not sender_id or not text:
            continue

        await _route_event(route_use_case, account_id, sender_id, text, event)

    return JSONResponse(status_code=200, content={"status": "ok"})


def _verify_signature(raw_body: bytes, signature_header: str | None, consumer_secret: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    if not consumer_secret:
        return False

    expected = "sha256=" + _hmac_sha256_base64(consumer_secret, raw_body.decode("utf-8"))
    return hmac.compare_digest(expected, signature_header)


async def _route_event(
    route_use_case: Any,
    account_id: str,
    sender_id: str,
    text: str,
    raw_event: Dict[str, Any],
) -> None:
    try:
        await route_use_case.execute(
            channel_type=CHANNEL_TYPE,
            external_id=account_id,
            external_conversation_key=sender_id,
            sender_id=sender_id,
            payload={"message": text, "raw": raw_event},
        )
    except ChannelMessageNotRoutable:
        logger.warning(
            "channels.twitter.not_routable",
            extra={"account_id": account_id, "sender_id": sender_id},
        )
    except Exception:
        logger.exception("channels.twitter.routing_failed")
