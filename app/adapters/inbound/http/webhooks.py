"""Generic inbound webhook, for callers that already speak the canonical envelope shape."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("http.webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class GenericWebhookRequest(BaseModel):
    """Request body for POST /webhooks/generic.

    Attributes:
        workflow_id (str): Id of the Langflow flow that should run.
        conversation_id (str): Id of the conversation.
        sender_id (Optional[str]): Id of the sender, if applicable.
        transport (str): Origin transport (rabbitmq, kafka, ...).
        channel (Optional[str]): Logical channel, if applicable.
        payload (Dict[str, Any]): Message payload.
    """

    workflow_id: str
    conversation_id: str
    sender_id: Optional[str] = None
    transport: str = "rabbitmq"
    channel: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.post("/generic")
async def generic_webhook(body: GenericWebhookRequest, request: Request):
    """Ingest a generic message and inject it into the pipeline.

    Builds an inbound MessageEnvelope from the request body via
    IngestMessageUseCase; used by n8n and other internal callers that
    do not have a dedicated channel webhook.

    Args:
        body (GenericWebhookRequest): The generic webhook request body.
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.ingest_message_use_case`.

    Returns:
        dict: A status dict acknowledging the message.

    Raises:
        HTTPException: 500 if ingestion fails.
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
