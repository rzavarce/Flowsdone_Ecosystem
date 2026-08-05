"""Port for generating shared secrets used to verify channel webhooks."""

from __future__ import annotations

from typing import Protocol


class SecretGeneratorPort(Protocol):
    """Generates opaque, cryptographically secure random secrets.

    Used wherever a channel needs a per-connection shared secret to
    verify inbound webhooks (e.g. Telegram's secret_token) without
    asking an admin to hand-roll one with `openssl rand -hex 32`.
    """

    def generate(self) -> str:
        """Generate a new random secret.

        Returns:
            str: A random secret, safe to use as a webhook
            verification token.
        """
        ...
