"""Shared bits of the 360dialog (WhatsApp Cloud API) integration: where
each connection's API lives and the names of the credentials it uses.
"""

from __future__ import annotations

from typing import Any, Dict

from app.core.config import settings

# Keys inside channel_connections.credentials for channel_type="whatsapp_360dialog".
API_KEY_FIELD = "api_key"
WEBHOOK_SECRET_FIELD = "d360_webhook_secret"
# Key inside channel_connections.config: true = 360dialog's sandbox host.
SANDBOX_FIELD = "sandbox"

# Header 360dialog sends back on every webhook call (configured with the
# webhook URL); no underscores, which 360dialog rejects in headers.
WEBHOOK_SECRET_HEADER = "X-Flowsdone-Webhook-Secret"


def is_sandbox(config: Dict[str, Any]) -> bool:
    """Whether a connection uses 360dialog's sandbox instead of production.

    Args:
        config (Dict[str, Any]): The connection's config.

    Returns:
        bool: True if `config["sandbox"]` is set to a truthy value.
    """
    return bool(config.get(SANDBOX_FIELD))


def messages_url(config: Dict[str, Any]) -> str:
    """URL of the send-message endpoint for a connection.

    Production and sandbox do not share the same path: production
    serves it at `/messages`, the sandbox at `/v1/messages`.

    Args:
        config (Dict[str, Any]): The connection's config.

    Returns:
        str: The absolute endpoint URL.
    """
    if is_sandbox(config):
        return f"{settings.D360_SANDBOX_API_BASE_URL}/v1/messages"
    return f"{settings.D360_API_BASE_URL}/messages"


def webhook_config_url(config: Dict[str, Any]) -> str:
    """URL of the endpoint that sets a number's webhook.

    Args:
        config (Dict[str, Any]): The connection's config.

    Returns:
        str: The absolute endpoint URL.
    """
    base = settings.D360_SANDBOX_API_BASE_URL if is_sandbox(config) else settings.D360_API_BASE_URL
    return f"{base}/v1/configs/webhook"


def callback_url(external_id: str) -> str:
    """Our public webhook URL for one 360dialog connection.

    Args:
        external_id (str): The connection's business number (digits).

    Returns:
        str: The URL 360dialog must call for that number.
    """
    return f"{settings.PUBLIC_BASE_URL}/webhooks/whatsapp-360dialog/{external_id}"
