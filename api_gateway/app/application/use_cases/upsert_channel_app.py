"""Use case for upserting a channel_app's shared provider credentials."""

from __future__ import annotations

from typing import Any, Dict

from app.domain.models.channel_app import ChannelApp
from app.domain.ports.outbound import ChannelAppRepositoryPort, SecretGeneratorPort

__all__ = ["UpsertChannelAppUseCase"]

# Providers whose inbound webhook verification needs a secret we control
# (Meta compares it against `hub.verify_token`). Twitter's CRC challenge
# and TikTok's signature scheme need no stored secret, so they're absent
# here and the caller's `credentials` pass through untouched.
AUTO_GENERATED_SECRET_FIELDS: Dict[str, str] = {
    "meta": "webhook_verify_token",
}


class UpsertChannelAppUseCase:
    """Creates or replaces a provider's shared app credentials,
    auto-generating the webhook verification secret when the provider
    needs one and the caller didn't supply it — so admins never have
    to hand-run `openssl rand -hex 32` before registering an app.

    Mirrors CreateChannelConnectionUseCase/UpdateChannelConnectionUseCase's
    auto-secret pattern, but keyed by provider instead of channel_type
    since channel_apps are shared per-provider, not per-connection.
    `ChannelAppRepositoryPort.upsert` replaces `credentials` wholesale,
    so an existing secret is preserved across updates unless the caller
    explicitly overrides it.
    """

    def __init__(
        self,
        channel_app_repo: ChannelAppRepositoryPort,
        secret_generator: SecretGeneratorPort,
    ) -> None:
        """Build the use case.

        Args:
            channel_app_repo (ChannelAppRepositoryPort): Repository
                used to read and persist the channel_app.
            secret_generator (SecretGeneratorPort): Generates the
                webhook verification secret when the provider needs
                one and neither the caller nor the existing row has it.
        """
        self._channel_app_repo = channel_app_repo
        self._secret_generator = secret_generator

    async def execute(
        self, *, provider: str, credentials: Dict[str, Any], config: Dict[str, Any]
    ) -> ChannelApp:
        """Upsert a channel_app, auto-securing its webhook verification
        secret when the provider supports one.

        Args:
            provider (str): Provider identifier (e.g. "meta").
            credentials (Dict[str, Any]): App credentials to encrypt
                and store. If the provider needs a webhook verification
                secret and this omits it, one is generated (or the
                previously stored value is preserved).
            config (Dict[str, Any]): Arbitrary app configuration.

        Returns:
            ChannelApp: The upserted channel app.
        """
        secret_field = AUTO_GENERATED_SECRET_FIELDS.get(provider)
        credentials = dict(credentials)

        if secret_field is not None and secret_field not in credentials:
            existing = await self._channel_app_repo.get_by_provider(provider)
            existing_value = existing.credentials.get(secret_field) if existing else None
            credentials[secret_field] = existing_value or self._secret_generator.generate()

        return await self._channel_app_repo.upsert(
            provider=provider, credentials=credentials, config=config
        )
