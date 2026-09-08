"""Inbound HTTP/WebSocket entry points for the voice channel.

Deliberately routed under a generic /webhooks/voice and /voice/stream
prefix rather than /webhooks/twilio - no provider name is exposed on
any public route, so switching or adding a voice provider later never
changes what is configured on the telephony side.
"""

from fastapi import APIRouter

from app.adapters.inbound.http.voice.handoff import router as handoff_router
from app.adapters.inbound.http.voice.stream import router as stream_router
from app.adapters.inbound.http.voice.webhook import router as webhook_router

router = APIRouter()

for _sub_router in (webhook_router, handoff_router, stream_router):
    router.include_router(_sub_router)
