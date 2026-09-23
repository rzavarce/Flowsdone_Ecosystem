"""Console authentication endpoints: login, current user and logout.

The session travels in an httpOnly cookie, so the frontend never touches
the token (no XSS exposure). The console and this API must share an
origin (nginx/Traefik route `/api` to the gateway), which is also why no
CORS is enabled. `SameSite=Lax` keeps the cookie off cross-site POSTs.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.adapters.inbound.http.auth_deps import get_current_user
from app.application.dto.auth_dto import AuthenticatedUser
from app.application.use_cases.activate_account import InvalidTokenError
from app.application.use_cases.authenticate_user import (
    InvalidCredentialsError,
    TooManyAttemptsError,
)
from app.application.use_cases.request_password_reset import (
    TooManyAttemptsError as TooManyResetAttemptsError,
)
from app.core.config import settings
from app.domain.ports.outbound import EmailSendError

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("auth.account")

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


class ActivateAccountRequest(BaseModel):
    """Body for `POST /auth/activate`.

    Attributes:
        token (str): Value from the activation link's URL.
        password (str): The password the user is choosing.
    """

    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=1, max_length=1024)


class ForgotPasswordRequest(BaseModel):
    """Body for `POST /auth/forgot-password`.

    Attributes:
        email (str): Account email to send the reset link to, if it exists.
    """

    email: str = Field(min_length=3, max_length=254)


class ResetPasswordRequest(BaseModel):
    """Body for `POST /auth/reset-password`.

    Attributes:
        token (str): Value from the reset link's URL.
        password (str): The new password.
    """

    token: str = Field(min_length=1, max_length=512)
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


async def _check_ip_throttle(request: Request, *, prefix: str) -> None:
    """Rate-limit an endpoint by client IP, reusing the shared login throttle.

    Defense in depth for `/auth/activate` and `/auth/reset-password`: the
    token itself is an unguessable 256-bit value, so this is about capping
    abuse/scraping, not brute-forcing the token.

    Args:
        request (Request): Used to read the client IP and reach the throttle.
        prefix (str): Namespaces the counter (e.g. `activate`, `reset`) so
            it can't be exhausted by traffic against another endpoint.

    Raises:
        HTTPException: 429 if the IP hit `AUTH_LOGIN_MAX_FAILURES_PER_IP`
            within `AUTH_LOGIN_WINDOW_SECONDS`.
    """
    ip = _client_ip(request)
    if not ip:
        return
    key = f"{prefix}:ip:{ip}"
    throttle = request.app.state.login_throttle
    if await throttle.failures(key) >= settings.AUTH_LOGIN_MAX_FAILURES_PER_IP:
        raise HTTPException(
            status_code=429,
            detail="too many attempts",
            headers={**_NO_STORE, "Retry-After": str(settings.AUTH_LOGIN_WINDOW_SECONDS)},
        )
    await throttle.record_failure(key, window_seconds=settings.AUTH_LOGIN_WINDOW_SECONDS)


@router.post("/activate", response_model=AuthenticatedUser)
async def activate_account(
    body: ActivateAccountRequest, request: Request, response: Response
) -> AuthenticatedUser:
    """Redeem an activation token, set the password and sign the user in.

    Args:
        body (ActivateAccountRequest): Token and chosen password.
        request (Request): Used to reach the use case and read the client IP.
        response (Response): Receives the session cookie.

    Returns:
        AuthenticatedUser: The now-active, signed-in user.

    Raises:
        HTTPException: 400 if the token is invalid/expired/already used, or
            the account is no longer pending, or the password is too short;
            429 when throttled.
    """
    response.headers.update(_NO_STORE)
    await _check_ip_throttle(request, prefix="activate")
    try:
        token, user = await request.app.state.activate_account_use_case.execute(
            token=body.token, password=body.password
        )
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="invalid or expired link", headers=_NO_STORE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=_NO_STORE)
    _set_session_cookie(response, token)
    return user


@router.post("/forgot-password", status_code=202)
async def forgot_password(body: ForgotPasswordRequest, request: Request, response: Response) -> None:
    """Request a password-reset email.

    Always answers 202, whether or not the email is registered - the point
    is that a caller cannot tell the difference (see
    `RequestPasswordResetUseCase`). A provider outage (`EmailSendError`) is
    logged but still answered as 202 for the same reason: a different
    status code for that case would itself reveal that the account exists.

    Args:
        body (ForgotPasswordRequest): The email to send the link to.
        request (Request): Used to reach the use case and read the client IP.
        response (Response): Receives no-store headers.

    Raises:
        HTTPException: 429 when throttled (this alone does not leak
            existence: the same limit applies per-IP regardless of email).
    """
    response.headers.update(_NO_STORE)
    try:
        await request.app.state.request_password_reset_use_case.execute(
            email=body.email, client_ip=_client_ip(request)
        )
    except TooManyResetAttemptsError:
        raise HTTPException(
            status_code=429,
            detail="too many attempts",
            headers={**_NO_STORE, "Retry-After": str(settings.AUTH_LOGIN_WINDOW_SECONDS)},
        )
    except EmailSendError as exc:
        logger.warning("auth.forgot_password.email_failed", extra={"error": str(exc)})


@router.post("/reset-password", response_model=AuthenticatedUser)
async def reset_password(
    body: ResetPasswordRequest, request: Request, response: Response
) -> AuthenticatedUser:
    """Redeem a reset token, set the new password and sign the user in.

    Args:
        body (ResetPasswordRequest): Token and new password.
        request (Request): Used to reach the use case and read the client IP.
        response (Response): Receives the session cookie.

    Returns:
        AuthenticatedUser: The signed-in user.

    Raises:
        HTTPException: 400 if the token is invalid/expired/already used, or
            the account is not active, or the password is too short; 429
            when throttled.
    """
    response.headers.update(_NO_STORE)
    await _check_ip_throttle(request, prefix="reset")
    try:
        token, user = await request.app.state.reset_password_use_case.execute(
            token=body.token, password=body.password
        )
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="invalid or expired link", headers=_NO_STORE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc), headers=_NO_STORE)
    _set_session_cookie(response, token)
    return user
