"""Public endpoint for the landing page's contact form (flowsdone.com).

No authentication: anyone can write. Abuse is kept down by a per-IP limit
(see `SendContactRequestUseCase`) and a honeypot field that people never
see and bots tend to fill in.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field

from app.adapters.inbound.http.auth import _client_ip
from app.application.use_cases.send_contact_request import ContactNotConfiguredError, TooManyContactRequestsError
from app.core.config import settings
from app.domain.models.contact import ContactRequest
from app.domain.ports.outbound import EmailSendError

logger = logging.getLogger("http.contact")

router = APIRouter(prefix="/public", tags=["public"])


class ContactForm(ContactRequest):
    """Request body of POST /public/contact.

    Attributes:
        website (Optional[str]): Honeypot: hidden in the form, so a value
            means a bot. The request is then accepted and silently dropped.
    """

    website: Optional[str] = Field(default=None, max_length=200)


@router.post("/contact", status_code=204)
async def send_contact(body: ContactForm, request: Request) -> Response:
    """Email a contact request to the Flowsdone team.

    Args:
        body (ContactForm): What the prospect wrote.
        request (Request): Used to reach `request.app.state.send_contact_request_use_case`
            and to read the client IP.

    Returns:
        Response: 204 when sent (also when the honeypot was filled in).

    Raises:
        HTTPException: 429 if the IP sent too many requests; 503 if the form
            is not configured; 502 if the email could not be sent.
    """
    if body.website:
        logger.info("contact.honeypot")
        return Response(status_code=204)
    try:
        await request.app.state.send_contact_request_use_case.execute(
            ContactRequest(**body.model_dump(exclude={"website"})), client_ip=_client_ip(request)
        )
    except TooManyContactRequestsError:
        raise HTTPException(
            status_code=429, detail="too many requests", headers={"Retry-After": str(settings.CONTACT_WINDOW_SECONDS)}
        )
    except ContactNotConfiguredError:
        raise HTTPException(status_code=503, detail="contact form not configured")
    except EmailSendError as exc:
        logger.warning("contact.email_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="could not send the message")
    return Response(status_code=204)
