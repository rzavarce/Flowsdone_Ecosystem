"""Shared helper for auto-registering a channel's webhook with its
external platform.

Used by both CreateChannelConnectionUseCase and
UpdateChannelConnectionUseCase, which each know *what* to roll back on
failure (delete the new row vs. restore the previous credentials) but
share the exact same "attempt registration, compensate, surface one
error type" mechanics.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from api_gateway.app.domain.ports.outbound import WebhookRegistrarPort

logger = logging.getLogger("usecase.webhook_registration")


class WebhookRegistrationError(Exception):
    """Raised when a channel's external webhook registration fails.

    By the time this is raised, the caller's compensating action has
    already run, so the channel_connection never ends up pointing at a
    secret the external platform doesn't actually know about.
    """


async def register_or_compensate(
    *,
    registrar: WebhookRegistrarPort,
    external_id: str,
    credentials: Dict[str, Any],
    channel_type: str,
    on_failure: Callable[[], Awaitable[None]],
) -> None:
    """Register a webhook, compensating if the platform rejects it.

    Args:
        registrar (WebhookRegistrarPort): Registrar to call.
        external_id (str): Channel-specific identifier (bot token,
            page id, ...).
        credentials (Dict[str, Any]): The channel_connection's
            credentials, from which the registrar reads whatever it
            needs (a generated secret, a page_access_token, ...).
        channel_type (str): Channel type, only used for logging.
        on_failure (Callable[[], Awaitable[None]]): Compensating
            action to run if registration fails (e.g. delete the row
            that was just created, or restore prior credentials).

    Raises:
        WebhookRegistrationError: If the external platform rejects the
            registration, after `on_failure()` has run.
    """
    try:
        await registrar.register(external_id=external_id, credentials=credentials)
    except Exception as exc:
        logger.error(
            "webhook_registration.failed",
            extra={"channel_type": channel_type},
        )
        await on_failure()
        raise WebhookRegistrationError(str(exc)) from exc

    logger.info("webhook_registration.succeeded", extra={"channel_type": channel_type})
