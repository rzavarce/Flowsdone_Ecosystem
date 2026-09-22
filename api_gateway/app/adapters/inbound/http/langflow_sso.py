"""Public endpoint that finishes the embedded-Langflow single sign-on.

The console gets a single-use ticket from `POST /internal/admin/langflow/session`
and loads `/langflow-sso?ticket=…` in the iframe. Here the ticket is redeemed,
the gateway logs in to Langflow as the tenant's user and sets Langflow's own
session cookies on the response, then redirects into the tenant's folder.

In production Traefik routes `agents.<domain>/langflow-sso` to the gateway, so
the cookies land on the same host Langflow is served from (host-only, no
`Domain`). Locally the gateway (`localhost:8000`) and Langflow
(`localhost:7860`) share cookies because cookies ignore the port.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.application.use_cases.langflow_sso import LangflowLanding
from app.core.config import settings
from app.domain.ports.outbound import LangflowSessionError

router = APIRouter(tags=["langflow-sso"])

# Lifetimes Langflow itself uses for its cookies (access 1 h, refresh 7 d).
_ACCESS_MAX_AGE = 3600
_REFRESH_MAX_AGE = 7 * 24 * 3600

_ERROR_PAGE = (
    "<!doctype html><meta charset=utf-8><title>Langflow</title>"
    "<body style='font-family:sans-serif;padding:2rem;color:#334155'>"
    "<p>{message}</p></body>"
)


def _error(status_code: int, message: str) -> HTMLResponse:
    """A minimal, non-cacheable error page (the iframe shows it as-is).

    Args:
        status_code (int): HTTP status.
        message (str): Text for the person looking at the frame.

    Returns:
        HTMLResponse: The response.
    """
    return HTMLResponse(
        _ERROR_PAGE.format(message=message),
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def _set_langflow_cookies(response: Response, landing: LangflowLanding) -> None:
    """Set the cookies Langflow's frontend reads.

    `access_token_lf` is readable by JS on purpose (Langflow's frontend reads
    it from `document.cookie`); the refresh token is httpOnly. `SameSite=Lax`
    is enough: the console and Langflow are the same *site* (sibling
    subdomains), so the cookies travel inside the iframe.

    Args:
        response (Response): Response to set the cookies on.
        landing (LangflowLanding): The tokens obtained for the tenant's user.
    """
    secure = settings.LANGFLOW_PUBLIC_URL.startswith("https://")
    response.set_cookie(
        "access_token_lf", landing.tokens.access_token, max_age=_ACCESS_MAX_AGE, path="/", samesite="lax", secure=secure
    )
    if landing.tokens.refresh_token:
        response.set_cookie(
            "refresh_token_lf",
            landing.tokens.refresh_token,
            max_age=_REFRESH_MAX_AGE,
            path="/",
            httponly=True,
            samesite="lax",
            secure=secure,
        )


@router.get("/langflow-sso", include_in_schema=False)
async def langflow_sso(request: Request, ticket: str = Query(default="", max_length=200)) -> Response:
    """Redeem an SSO ticket and redirect into Langflow, logged in.

    Args:
        request (Request): The incoming FastAPI request; used to reach
            `request.app.state.redeem_langflow_ticket_use_case`.
        ticket (str): The single-use ticket from the console.

    Returns:
        Response: A 303 redirect to the tenant's Langflow folder with Langflow's
        session cookies; or a small error page (400 invalid/expired ticket,
        502 Langflow failed).
    """
    try:
        landing = await request.app.state.redeem_langflow_ticket_use_case.execute(ticket)
    except LangflowSessionError:
        return _error(502, "No se pudo abrir Langflow. Vuelve a intentarlo en unos segundos.")
    if landing is None:
        return _error(400, "El enlace caducó o ya se usó. Recarga la página de Agentes.")
    response = RedirectResponse(f"{settings.LANGFLOW_PUBLIC_URL}{landing.path}", status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    _set_langflow_cookies(response, landing)
    return response
