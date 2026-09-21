"""Console authentication endpoints: login, current user and logout.

The session travels in an httpOnly cookie, so the frontend never touches
the token (no XSS exposure). The console and this API must share an
origin (nginx/Traefik route `/api` to the gateway), which is also why no
CORS is enabled. `SameSite=Lax` keeps the cookie off cross-site POSTs.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.adapters.inbound.http.auth_deps import get_current_user
from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases.authenticate_user import (
    InvalidCredentialsError,
    TooManyAttemptsError,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_NO_STORE = {"Cache-Control": "no-store"}


class LoginRequest(BaseModel):
    """Credentials submitted by the login form.

    Attributes:
        email (str): Account email (case-insensitive).
        password (str): Plaintext password over TLS; length is capped so
            a huge body cannot be used to burn CPU in the hasher.
    """

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


def _cookie_secure() -> bool:
    """Whether to mark the cookie `Secure` (HTTPS only).

    Returns:
        bool: `settings.AUTH_COOKIE_SECURE` if set, else True only when
        `PUBLIC_BASE_URL` is https, so plain-http local dev still works.
    """
    if settings.AUTH_COOKIE_SECURE is not None:
        return settings.AUTH_COOKIE_SECURE
    return settings.PUBLIC_BASE_URL.lower().startswith("https://")


def _set_session_cookie(response: Response, token: str) -> None:
    """Attach the session cookie (httpOnly, SameSite=Lax) to a response."""
    response.set_cookie(
        settings.AUTH_COOKIE_NAME,
        token,
        max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def _client_ip(request: Request) -> Optional[str]:
    """Best-effort client IP for the per-IP throttle.

    Args:
        request (Request): The incoming request.

    Returns:
        Optional[str]: First `X-Forwarded-For` hop when
        `AUTH_TRUST_FORWARDED_FOR` is on and the header is present,
        otherwise the socket peer address.
    """
    if settings.AUTH_TRUST_FORWARDED_FOR:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip() or None
    return request.client.host if request.client else None


@router.post("/login", response_model=AuthenticatedUser)
async def login(body: LoginRequest, request: Request, response: Response) -> AuthenticatedUser:
    """Sign in and set the session cookie.

    Args:
        body (LoginRequest): Email and password.
        request (Request): Used to reach the use case and read the client IP.
        response (Response): Receives the session cookie.

    Returns:
        AuthenticatedUser: The signed-in user and their tenants.

    Raises:
        HTTPException: 401 for wrong credentials or a disabled account
            (indistinguishable on purpose); 429 when throttled.
    """
    response.headers.update(_NO_STORE)
    try:
        token, user = await request.app.state.authenticate_user_use_case.execute(
            email=body.email, password=body.password, client_ip=_client_ip(request)
        )
    except TooManyAttemptsError:
        raise HTTPException(
            status_code=429,
            detail="too many attempts",
            headers={**_NO_STORE, "Retry-After": str(settings.AUTH_LOGIN_WINDOW_SECONDS)},
        )
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="invalid credentials", headers=_NO_STORE)
    _set_session_cookie(response, token)
    return user


@router.get("/me", response_model=AuthenticatedUser)
async def me(
    request: Request,
    response: Response,
    user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Return the signed-in user; also renews the cookie's lifetime.

    Args:
        request (Request): Source of the current session cookie.
        response (Response): Receives the renewed cookie.
        user (AuthenticatedUser): Resolved by `get_current_user` (401 if
            there is no valid session).

    Returns:
        AuthenticatedUser: The signed-in user and their tenants.
    """
    response.headers.update(_NO_STORE)
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if token:
        _set_session_cookie(response, token)
    return user


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response) -> None:
    """Close the session server-side and clear the cookie (idempotent).

    Args:
        request (Request): Source of the session cookie.
        response (Response): Receives the cookie-clearing header.
    """
    await request.app.state.logout_user_use_case.execute(
        request.cookies.get(settings.AUTH_COOKIE_NAME)
    )
    response.headers.update(_NO_STORE)
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
