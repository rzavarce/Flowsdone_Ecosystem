"""Public API a client's CRM calls during a handoff: send the agent's
reply to the contact, and close the handoff (the bot takes over again).

Authenticated per integration with the `X-Api-Key` header (the
integration's api_key).
"""

from __future__ import annotations

import hmac
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.use_cases.crm_handoff import HandoffNotOpenError, OutsideMessagingWindowError
from app.domain.models.crm import CrmIntegration

logger = logging.getLogger("crm.api")

router = APIRouter(prefix="/integrations/crm", tags=["crm"])


class CrmReplyIn(BaseModel):
    """Body of POST /integrations/crm/{integration_id}/messages.

    Attributes:
        conversation_id (str): The conversation_id received in our events.
        text (str): The agent's message.
    """

    conversation_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=4096)


class CrmCloseIn(BaseModel):
    """Body of POST /integrations/crm/{integration_id}/close.

    Attributes:
        conversation_id (str): The conversation_id received in our events.
    """

    conversation_id: str = Field(min_length=1)


async def _authenticate(request: Request, integration_id: UUID, api_key: Optional[str]) -> CrmIntegration:
    """Check the caller holds the integration's API key.

    Args:
        request (Request): The request (reaches app.state).
        integration_id (UUID): The integration in the path.
        api_key (Optional[str]): The X-Api-Key header.

    Returns:
        CrmIntegration: The integration.

    Raises:
        HTTPException: 401 if the integration is unknown or the key wrong
            (indistinguishable on purpose), 403 if it is inactive.
    """
    integration = await request.app.state.crm_integration_repo.get(integration_id)
    expected = (integration.credentials.get("api_key") if integration else None) or ""
    if not expected or not hmac.compare_digest((api_key or "").encode(), expected.encode()):
        logger.warning("crm.api.unauthorized", extra={"integration_id": str(integration_id)})
        raise HTTPException(status_code=401, detail="invalid api key")
    if integration.status != "active":
        raise HTTPException(status_code=403, detail="integration inactive")
    return integration


@router.post("/{integration_id}/messages", status_code=202)
async def reply(
    integration_id: UUID,
    body: CrmReplyIn,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
) -> dict:
    """Send the agent's reply to the contact, on the contact's channel.

    Args:
        integration_id (UUID): The integration.
        body (CrmReplyIn): Conversation and message.
        request (Request): The request.
        x_api_key (Optional[str]): The integration's API key.

    Returns:
        dict: {"status": "sent"}.

    Raises:
        HTTPException: 401/403 (see _authenticate), 409 if the conversation
            is not handed over to this integration (closed, expired...),
            422 if the channel's messaging window is closed.
    """
    integration = await _authenticate(request, integration_id, x_api_key)
    try:
        await request.app.state.reply_from_crm_use_case.execute(
            integration_id=integration.id, conversation_id=body.conversation_id, text=body.text
        )
    except HandoffNotOpenError as exc:
        raise HTTPException(status_code=409, detail="conversation is not handed over to this integration") from exc
    except OutsideMessagingWindowError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "messaging_window_closed", "allowed": exc.decision.mode},
        ) from exc
    return {"status": "sent"}


@router.post("/{integration_id}/close")
async def close(
    integration_id: UUID,
    body: CrmCloseIn,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
) -> dict:
    """Close the handoff: the conversation goes back to the bot.

    Args:
        integration_id (UUID): The integration.
        body (CrmCloseIn): The conversation.
        request (Request): The request.
        x_api_key (Optional[str]): The integration's API key.

    Returns:
        dict: {"status": "closed"}.

    Raises:
        HTTPException: 401/403 (see _authenticate), 409 if the conversation
            is not handed over to this integration.
    """
    integration = await _authenticate(request, integration_id, x_api_key)
    try:
        await request.app.state.close_handoff_use_case.execute(
            integration_id=integration.id, conversation_id=body.conversation_id
        )
    except HandoffNotOpenError as exc:
        raise HTTPException(status_code=409, detail="conversation is not handed over to this integration") from exc
    return {"status": "closed"}
