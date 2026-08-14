"""Internal endpoint used by the outbound workers to deliver a response
back to the gateway process that holds the live WebSocket/channel state.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request

from ....application.services.hmac_signing import verify
from ....core.config import settings
from ....domain.models.message_envelope import MessageEnvelope

logger = logging.getLogger("internal.outbound")

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_hmac(body: bytes, signature: str | None) -> bool:
    """Verify the HMAC-SHA256 signature of an internal request body.

    Thin wrapper around the shared
    `application.services.hmac_signing.verify`, kept as a
    module-level function for backward compatibility with existing
    callers/tests.

    Args:
        body (bytes): Raw request body bytes.
        signature (str | None): Value of the X-Signature header.

    Returns:
        bool: True if the signature is present and valid.
    """
    return verify(body, signature, settings.CALLBACK_HMAC_SECRET)


@router.post("/outbound", status_code=202)
async def receive_outbound(
    request: Request,
    x_signature: str | None = Header(default=None),
):
    """Receive an outbound envelope from a worker and deliver it.

    Called by kafka_outbound_worker/rabbitmq_outbound_worker after they
    consume an outbound MessageEnvelope from the broker; this endpoint
    runs inside the actual gateway process, so it has access to the
    real WSRegistry and channel senders.

    Args:
        request (Request): The incoming FastAPI request.
        x_signature (str | None): HMAC-SHA256 signature of the body,
            signed with settings.CALLBACK_HMAC_SECRET.

    Returns:
        dict: A status dict indicating whether the envelope was
        accepted or ignored (non-outbound direction).

    Raises:
        HTTPException: 401 if the signature is missing or invalid.
    """
    raw = await request.body()

    if not verify_hmac(raw, x_signature):
        logger.error("internal.outbound.unauthorized")
        raise HTTPException(status_code=401, detail="invalid signature")

    data = await request.json()
    envelope = MessageEnvelope.model_validate(data)

    if envelope.meta.direction != "outbound":
        return {"status": "ignored"}

    await request.app.state.outbound_handler.deliver(envelope)

    return {"status": "accepted"}
