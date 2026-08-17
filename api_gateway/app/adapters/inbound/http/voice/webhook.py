"""Incoming call webhook: the first HTTP request a voice provider makes
when a call arrives, before the real-time streaming WebSocket connects.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response

from api_gateway.app.core.config import settings
from api_gateway.app.domain.models.call_session import CallSession

logger = logging.getLogger("channels.voice.webhook")

router = APIRouter(prefix="/webhooks/voice", tags=["channels:voice"])

CHANNEL_TYPE = "voice"
APP_PROVIDER = "twilio"

# Minimal static TwiML for calls we cannot route (unknown number, no
# app credentials, invalid signature). Not provider-abstracted like
# the happy path: it is a fixed, trivial markup fragment, not worth a
# VoiceProviderPort method of its own.
_REJECT_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>'


def _external_url(request: Request) -> str:
    """Build the externally-visible URL the voice provider called.

    Uses settings.PUBLIC_BASE_URL rather than request.url, since this
    process sits behind a reverse proxy and the provider's webhook
    signature is computed against the public URL it actually called.

    Args:
        request (Request): The incoming FastAPI request.

    Returns:
        str: The public URL, e.g. "https://platform.flowsdone.com/webhooks/voice".
    """
    return f"{settings.PUBLIC_BASE_URL}{request.url.path}"


def _stream_url(call_sid: str) -> str:
    """Build the wss:// URL the provider should stream this call to.

    Args:
        call_sid (str): Provider-assigned unique id for the call.

    Returns:
        str: The streaming WebSocket URL, derived from
        settings.PUBLIC_BASE_URL.
    """
    ws_base = settings.PUBLIC_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    return f"{ws_base}/voice/stream/{call_sid}"


def _handoff_url() -> str:
    """Build the URL the provider calls with fresh instructions once
    the streaming session ends (human transfer, see handoff.py).

    Returns:
        str: The handoff webhook URL, derived from settings.PUBLIC_BASE_URL.
    """
    return f"{settings.PUBLIC_BASE_URL}/webhooks/voice/handoff"


@router.post("")
async def receive_call(request: Request) -> Response:
    """Handle an incoming call: verify it, open a call session, and
    hand the call off to the real-time streaming endpoint.

    Args:
        request (Request): The incoming FastAPI request, form-encoded
            with (at least) To/From/CallSid/AccountSid.

    Returns:
        Response: TwiML (or another provider's equivalent call-control
        markup) connecting the call to /voice/stream/{call_sid}, or a
        reject response if the call cannot be routed.
    """
    form = await request.form()
    form_params = {key: str(value) for key, value in form.items()}

    to_number = form_params.get("To")
    from_number = form_params.get("From")
    call_sid = form_params.get("CallSid")

    if not to_number or not from_number or not call_sid:
        logger.warning("channels.voice.missing_call_params")
        return Response(content=_REJECT_TWIML, media_type="application/xml", status_code=400)

    channel_app_repo = request.app.state.channel_app_repo
    channel_app = await channel_app_repo.get_by_provider(APP_PROVIDER)
    auth_token = channel_app.credentials.get("auth_token") if channel_app else None

    voice_provider = request.app.state.voice_provider
    signature = request.headers.get("X-Twilio-Signature", "")

    if not auth_token or not voice_provider.verify_webhook_signature(
        url=_external_url(request),
        form_params=form_params,
        signature=signature,
        auth_token=auth_token,
    ):
        logger.warning("channels.voice.invalid_signature", extra={"call_sid": call_sid})
        return Response(content=_REJECT_TWIML, media_type="application/xml", status_code=401)

    channel_connection_repo = request.app.state.channel_connection_repo
    resolution = await channel_connection_repo.get_by_channel_and_external_id(
        CHANNEL_TYPE, to_number
    )

    if resolution is None:
        logger.warning("channels.voice.not_routable", extra={"to": to_number})
        return Response(content=_REJECT_TWIML, media_type="application/xml", status_code=404)

    voice_config = resolution.config or {}

    session = CallSession(
        call_sid=call_sid,
        channel_connection_id=resolution.channel_connection_id,
        project_id=resolution.project_id,
        agent_id=resolution.agent_id,
        langflow_flow_id=resolution.langflow_flow_id,
        from_number=from_number,
        to_number=to_number,
        provider=APP_PROVIDER,
        status="ringing",
        started_at=datetime.now(timezone.utc),
        config=voice_config,
    )

    call_session_repo = request.app.state.call_session_repo
    await call_session_repo.save(session, ttl_seconds=settings.CALL_SESSION_TTL_SECONDS)

    logger.info(
        "channels.voice.call.accepted",
        extra={"call_sid": call_sid, "project_id": str(resolution.project_id)},
    )

    # Only ask Twilio to call us back post-session (action_url) when this
    # connection actually has somewhere to transfer to - no point paying
    # for the extra webhook round trip otherwise.
    action_url = _handoff_url() if voice_config.get("human_transfer_number") else None

    twiml = voice_provider.build_twiml_connect(
        stream_url=_stream_url(call_sid),
        voice=voice_config.get("voice"),
        language=voice_config.get("language"),
        tts_provider=voice_config.get("tts_provider"),
        transcription_language=voice_config.get("transcription_language"),
        transcription_provider=voice_config.get("transcription_provider"),
        speech_model=voice_config.get("speech_model"),
        action_url=action_url,
    )
    return Response(content=twiml, media_type="application/xml")
