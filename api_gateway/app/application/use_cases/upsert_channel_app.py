"""Use case for upserting a channel_app's shared provider credentials."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from app.domain.models.channel_app import ChannelApp
from app.domain.ports.outbound import ChannelAppRepositoryPort, SecretGeneratorPort

__all__ = ["UpsertChannelAppUseCase"]

# Providers whose inbound webhook verification needs a secret we control
# (Meta compares it against `hub.verify_token`). Twitter's CRC challenge
# and TikTok's signature scheme need no stored secret, so they're absent
# here and the caller's `credentials` pass through untouched.
AUTO_GENERATED_SECRET_FIELDS: Dict[str, str] = {
    "meta": "webhook_verify_token",
    # Chatwoot: token in the Agent Bot's outgoing_url (see channels/chatwoot).
    "chatwoot": "webhook_token",
}

# Values the gateway itself writes into a channel_app after setting it up
# (e.g. the Chatwoot Agent Bot it creates). An admin's upsert never sends
# them, so they are carried over instead of being wiped out.
SERVER_MANAGED_FIELDS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "chatwoot": {"credentials": ("bot_access_token",), "config": ("bot_id",)},
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
                Gateway-managed values (SERVER_MANAGED_FIELDS) the caller
                omits are carried over from the stored app, in both
                `credentials` and `config`.

        Returns:
            ChannelApp: The upserted channel app.
        """
        secret_field = AUTO_GENERATED_SECRET_FIELDS.get(provider)
        managed = SERVER_MANAGED_FIELDS.get(provider, {})
        credentials = dict(credentials)
        config = dict(config)
        existing = None
        if secret_field is not None or managed:
            existing = await self._channel_app_repo.get_by_provider(provider)

        if secret_field is not None and secret_field not in credentials:
            existing_value = existing.credentials.get(secret_field) if existing else None
            credentials[secret_field] = existing_value or self._secret_generator.generate()

        # Gateway-managed values the caller did not send survive the upsert.
        if existing is not None:
            for key in managed.get("credentials", ()):
                if key not in credentials and key in existing.credentials:
                    credentials[key] = existing.credentials[key]
            for key in managed.get("config", ()):
                if key not in config and key in existing.config:
                    config[key] = existing.config[key]

        return await self._channel_app_repo.upsert(
            provider=provider, credentials=credentials, config=config
        )
