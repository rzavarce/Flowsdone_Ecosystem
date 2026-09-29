"""Token endpoint for the demo page's "Call" tab (browser softphone).

Lets someone place a WebRTC call into an agent's voice channel from the
browser (Twilio Voice JS SDK) instead of a phone. The demo's TwiML
Application points its Voice Request URL at the same /webhooks/voice used
for real calls, so no call-handling logic is duplicated here: this only
issues the Access Token the SDK needs, plus the number to dial.

The token lets the browser place calls on the Twilio account, so it is only
issued to whoever holds a valid demo link - a share link (?share=) or a
console test token (?test_token=) - and the number is the voice channel of
that link's agent (see ResolveVoiceDemoTargetUseCase).
"""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from app.core.config import settings

router = APIRouter(prefix="/voice-demo", tags=["voice-demo"])

_TOKEN_TTL_SECONDS = 3600
# Twilio client identities: keep them short and plain.
_IDENTITY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@router.get("/token")
async def issue_demo_token(
    request: Request,
    share: Optional[str] = Query(default=None),
    test_token: Optional[str] = Query(default=None),
    identity: str = Query(default="demo-softphone"),
) -> dict:
    """Issue a short-lived Twilio Access Token and the number to call.

    Args:
        request (Request): Used to reach `request.app.state.voice_demo_target_use_case`.
        share (Optional[str]): A share link's token.
        test_token (Optional[str]): A console test token.
        identity (str): Client identity for the token; only labels the
            caller in the Twilio console.

    Returns:
        dict: `{"token", "identity", "ttl_seconds", "to_number"}`.

    Raises:
        HTTPException: 404 if the voice demo is not configured (VOICE_DEMO_TWILIO_*
            unset), or the link is not valid or its agent has no active voice
            channel - the page then just doesn't offer the call; 422 on a
            malformed identity.
    """
    if not (
        settings.VOICE_DEMO_TWILIO_ACCOUNT_SID
        and settings.VOICE_DEMO_TWILIO_API_KEY_SID
        and settings.VOICE_DEMO_TWILIO_API_KEY_SECRET
        and settings.VOICE_DEMO_TWILIO_TWIML_APP_SID
    ):
        raise HTTPException(status_code=404, detail="voice demo not configured")
    if not _IDENTITY.match(identity):
        raise HTTPException(status_code=422, detail="invalid identity")

    target = await request.app.state.voice_demo_target_use_case.execute(share_token=share, test_token=test_token)
    if target is None:
        raise HTTPException(status_code=404, detail="no voice agent for this link")

    grant = VoiceGrant(
        outgoing_application_sid=settings.VOICE_DEMO_TWILIO_TWIML_APP_SID,
        incoming_allow=False,
    )
    token = AccessToken(
        settings.VOICE_DEMO_TWILIO_ACCOUNT_SID,
        settings.VOICE_DEMO_TWILIO_API_KEY_SID,
        settings.VOICE_DEMO_TWILIO_API_KEY_SECRET,
        identity=identity,
        ttl=_TOKEN_TTL_SECONDS,
    )
    token.add_grant(grant)

    return {
        "token": token.to_jwt(),
        "identity": identity,
        "ttl_seconds": _TOKEN_TTL_SECONDS,
        "to_number": target.to_number,
    }
