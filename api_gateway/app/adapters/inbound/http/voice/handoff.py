"""Human transfer webhook: the request the voice provider makes once a
ConversationRelay session ends with handoff data, expecting fresh
call-control instructions in response (see stream.py, which decides to
end the session and sends the handoff data through the WebSocket).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, Response

from app.core.config import settings

logger = logging.getLogger("channels.voice.handoff")

router = APIRouter(prefix="/webhooks/voice", tags=["channels:voice"])

APP_PROVIDER = "twilio"

_REJECT_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>'


@router.post("/handoff")
async def receive_handoff(request: Request) -> Response:
    """Handle the call-control callback that follows a ConversationRelay
    session ending with handoff data, and transfer the call to the
    phone number carried in that data.

    Args:
        request (Request): The incoming FastAPI request, form-encoded,
            including `HandoffData` (the JSON string we sent over the
            streaming WebSocket in stream.py).

    Returns:
        Response: TwiML that dials the human agent's number, or a
        reject response if the request cannot be verified/parsed.
    """
    form = await request.form()
    form_params = {key: str(value) for key, value in form.items()}

    channel_app_repo = request.app.state.channel_app_repo
    channel_app = await channel_app_repo.get_by_provider(APP_PROVIDER)
    auth_token = channel_app.credentials.get("auth_token") if channel_app else None

    voice_provider = request.app.state.voice_provider
    signature = request.headers.get("X-Twilio-Signature", "")
    url = f"{settings.PUBLIC_BASE_URL}{request.url.path}"

    if not auth_token or not voice_provider.verify_webhook_signature(
        url=url, form_params=form_params, signature=signature, auth_token=auth_token
    ):
        logger.warning("channels.voice.handoff.invalid_signature")
        return Response(content=_REJECT_TWIML, media_type="application/xml", status_code=401)

    try:
        handoff_data = json.loads(form_params.get("HandoffData", "{}"))
        transfer_number = handoff_data["transfer_number"]
    except (ValueError, KeyError):
        logger.error("channels.voice.handoff.invalid_data", extra={"raw": form_params.get("HandoffData")})
        return Response(content=_REJECT_TWIML, media_type="application/xml", status_code=400)

    logger.info("channels.voice.handoff.transferring", extra={"transfer_number": transfer_number})

    twiml = voice_provider.build_handoff_twiml(
        phone_number=transfer_number, caller_id=handoff_data.get("caller_id")
    )
    return Response(content=twiml, media_type="application/xml")
