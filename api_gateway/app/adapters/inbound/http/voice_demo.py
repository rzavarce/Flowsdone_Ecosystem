"""Token endpoint for the browser-based voice demo softphone.

Dev/testing tooling only - lets someone place a WebRTC call into the
voice channel from a browser (via the Twilio Voice JS SDK) instead of
a real phone, so the pipeline built in adapters/inbound/http/voice/ can
be exercised without carrier minutes. Deliberately kept separate from
that package: this issues an Access Token for Twilio's Voice SDK, it
does not participate in call routing (the demo's TwiML Application
points its Voice Request URL at the same /webhooks/voice used for real
calls, so no call-handling logic is duplicated here).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant

from api_gateway.app.core.config import settings

router = APIRouter(prefix="/voice-demo", tags=["voice-demo"])

_TOKEN_TTL_SECONDS = 3600


@router.get("/token")
async def issue_demo_token(identity: str = Query(default="softphone-demo")) -> dict:
    """Issue a short-lived Twilio Access Token for the Voice JS SDK.

    Args:
        identity (str): Client identity to embed in the token; only
            used to label the demo caller in the Twilio console.

    Returns:
        dict: `{"token": <jwt>, "identity": <identity>, "ttl_seconds": <int>}`.

    Raises:
        HTTPException: 404 if the voice demo is not configured
            (VOICE_DEMO_TWILIO_* settings unset) - this is dev-only
            tooling, so an unconfigured demo should not look like a
            server error.
    """
    if not (
        settings.VOICE_DEMO_TWILIO_ACCOUNT_SID
        and settings.VOICE_DEMO_TWILIO_API_KEY_SID
        and settings.VOICE_DEMO_TWILIO_API_KEY_SECRET
        and settings.VOICE_DEMO_TWILIO_TWIML_APP_SID
    ):
        raise HTTPException(status_code=404, detail="voice demo not configured")

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

    return {"token": token.to_jwt(), "identity": identity, "ttl_seconds": _TOKEN_TTL_SECONDS}
