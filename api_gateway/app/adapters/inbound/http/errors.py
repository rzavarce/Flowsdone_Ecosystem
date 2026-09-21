"""Mapping of domain errors to HTTP responses, shared by the app and its tests."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.ports.outbound import AlreadyExistsError


async def _already_exists(_: Request, exc: AlreadyExistsError) -> JSONResponse:
    """`AlreadyExistsError` -> 409 with a message the console can show."""
    return JSONResponse(status_code=409, content={"detail": "already exists"})


def register_error_handlers(app: FastAPI) -> None:
    """Attach the domain-error handlers to an app.

    Args:
        app (FastAPI): The application (or a test app) to configure.
    """
    app.add_exception_handler(AlreadyExistsError, _already_exists)  # type: ignore[arg-type]
