"""Startup safety checks for the production environment.

In production (`ENV=production`, exported by the deploy workflow) the
gateway:

- hides the interactive API documentation (`/docs`, `/redoc`,
  `/openapi.json`), which would publish every route and model;
- refuses to start if a shared secret still has its code default or the
  placeholder from `env.example.txt`, so a missing or copied `.env` value
  can never leave the admin API behind a well-known key.

Anywhere else (local, tests) nothing changes.
"""

from __future__ import annotations

from typing import Any, List

PRODUCTION = "production"

# Secrets that must be set to a real value in production, and the values
# known to be public (code defaults and env.example.txt placeholders).
_WEAK_SECRETS = {
    "ADMIN_API_KEY": {"dev-admin-key-change-me", "ChangeMeAdminApiKey123!"},
    "CALLBACK_HMAC_SECRET": {"dev-secret-change-me", "ChangeMeCallbackHmacSecret123"},
}
_MIN_SECRET_LENGTH = 24


class InsecureConfigurationError(RuntimeError):
    """Production settings that must not be used (the gateway won't start)."""


def is_production(settings: Any) -> bool:
    """Whether the gateway runs as the production environment.

    Args:
        settings (Any): `app.core.config.settings`.

    Returns:
        bool: True if `ENV` is "production" (case-insensitive).
    """
    return str(getattr(settings, "ENV", "")).strip().lower() == PRODUCTION


def api_docs_urls(settings: Any) -> dict:
    """FastAPI's documentation URLs for this environment.

    Args:
        settings (Any): `app.core.config.settings`.

    Returns:
        dict: `docs_url`, `redoc_url` and `openapi_url` for `FastAPI(...)`:
        all None in production (no public API map), FastAPI's defaults
        elsewhere.
    """
    if is_production(settings):
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def insecure_secrets(settings: Any) -> List[str]:
    """Shared secrets with a known, empty or too short value.

    Args:
        settings (Any): `app.core.config.settings`.

    Returns:
        List[str]: The names of the offending settings (never their values).
    """
    problems = []
    for name, weak in _WEAK_SECRETS.items():
        value = str(getattr(settings, name, "") or "")
        if value in weak or len(value) < _MIN_SECRET_LENGTH:
            problems.append(name)
    return problems


def check_production_settings(settings: Any) -> None:
    """Abort the start in production if a secret is not safe.

    Args:
        settings (Any): `app.core.config.settings`.

    Raises:
        InsecureConfigurationError: In production, if any shared secret is
            a default/placeholder, empty or shorter than 24 characters.
    """
    if not is_production(settings):
        return
    problems = insecure_secrets(settings)
    if problems:
        raise InsecureConfigurationError(
            "Refusing to start in production: set a strong, unique value (24+ characters) for "
            + ", ".join(problems)
            + " in the server's .env."
        )
