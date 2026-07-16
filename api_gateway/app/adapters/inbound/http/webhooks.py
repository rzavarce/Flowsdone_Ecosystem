from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("http.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------

class GenericWebhookRequest(BaseModel):
    workflow_id: str
    conversation_id: str
    sender_id: Optional[str] = None
    transport: str = "rabbitmq"
    channel: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------

@router.post("/generic")
async def generic_webhook(body: GenericWebhookRequest, request: Request):
    """
    Recibe un mensaje genérico por HTTP y lo inyecta al pipeline como
    MessageEnvelope en dirección 'inbound'.
    """
    try:
        use_case = request.app.state.ingest_message_use_case

        await use_case.execute(
            workflow_id=body.workflow_id,
            conversation_id=body.conversation_id,
            sender_id=body.sender_id,
            transport=body.transport,
            payload=body.payload,
            channel=body.channel,
        )

        logger.info(
            "webhook.generic.accepted",
            extra={
                "workflow_id": body.workflow_id,
                "conversation_id": body.conversation_id,
                "transport": body.transport,
            },
        )

        return {"status": "accepted"}

    except Exception as e:
        logger.error("webhook.generic.failed", exc_info=e)
        raise HTTPException(status_code=500, detail="failed to ingest message")