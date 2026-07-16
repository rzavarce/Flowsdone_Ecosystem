import hmac
import hashlib
import logging

from fastapi import APIRouter, Request, Header, HTTPException

from ....domain.models.message_envelope import MessageEnvelope
from ....core.config import settings

logger = logging.getLogger("internal.outbound")

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_hmac(body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        settings.CALLBACK_HMAC_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/outbound", status_code=202)
async def receive_outbound(
    request: Request,
    x_signature: str | None = Header(default=None),
):
    raw = await request.body()

    if not verify_hmac(raw, x_signature):
        logger.error("internal.outbound.unauthorized")
        raise HTTPException(status_code=401, detail="invalid signature")

    data = await request.json()
    envelope = MessageEnvelope.model_validate(data)

    # Solo procesamos outbound
    if envelope.meta.direction != "outbound":
        return {"status": "ignored"}

    # Entrega usando el handler REAL del gateway (tiene ws_registry real)
    await request.app.state.outbound_handler.deliver(envelope)

    return {"status": "accepted"}
