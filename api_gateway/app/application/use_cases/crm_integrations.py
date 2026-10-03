"""Use cases to set up a project's CRM integration from the console."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import UUID, uuid4

from app.domain.models.crm import CrmEvent, CrmIntegration
from app.domain.ports.outbound import (
    CrmIntegrationRepositoryPort,
    CrmProviderPort,
    SecretGeneratorPort,
)

logger = logging.getLogger("usecase.crm_integrations")

SIGNING_SECRET = "signing_secret"
API_KEY = "api_key"


class InvalidCrmIntegrationError(ValueError):
    """The integration's settings are not usable (e.g. a URL we may not call)."""


class ManageCrmIntegrationsUseCase:
    """Create, update, re-key and test CRM integrations.

    The gateway generates both secrets of an integration: the signing
    secret (we sign our events with it) and the API key (the CRM sends it
    with its replies). They are returned only when created or rotated.
    """

    def __init__(
        self,
        *,
        integrations: CrmIntegrationRepositoryPort,
        secret_generator: SecretGeneratorPort,
        ensure_allowed: Callable[[str], Awaitable[None]],
        providers: Dict[str, CrmProviderPort],
    ) -> None:
        """Build the use case.

        Args:
            integrations (CrmIntegrationRepositoryPort): Storage.
            secret_generator (SecretGeneratorPort): Generates the secrets.
            ensure_allowed (Callable[[str], Awaitable[None]]): Refuses URLs
                the gateway may not call (raises).
            providers (Dict[str, CrmProviderPort]): Adapters, to send a
                test event right away.
        """
        self._integrations = integrations
        self._secrets = secret_generator
        self._ensure_allowed = ensure_allowed
        self._providers = providers

    async def create(
        self, *, tenant_id: UUID, project_id: UUID, provider: str, config: Dict[str, Any]
    ) -> CrmIntegration:
        """Create a project's integration with fresh secrets.

        Args:
            tenant_id (UUID): Owning tenant.
            project_id (UUID): Project (one integration each).
            provider (str): CRM provider.
            config (Dict[str, Any]): Settings (for "generic_webhook", `url`).

        Returns:
            CrmIntegration: The integration, secrets included.

        Raises:
            InvalidCrmIntegrationError: If the settings are not usable.
            AlreadyExistsError: If the project already has an integration.
        """
        config = await self._validated(provider, config)
        return await self._integrations.create(
            tenant_id=tenant_id,
            project_id=project_id,
            provider=provider,
            config=config,
            credentials=self._new_secrets(),
        )

    async def update(
        self, integration: CrmIntegration, *, config: Optional[Dict[str, Any]] = None, status: Optional[str] = None
    ) -> Optional[CrmIntegration]:
        """Change an integration's settings or status.

        Args:
            integration (CrmIntegration): The integration.
            config (Optional[Dict[str, Any]]): New settings (merged onto the
                current ones).
            status (Optional[str]): "active" or "inactive".

        Returns:
            Optional[CrmIntegration]: The updated integration.

        Raises:
            InvalidCrmIntegrationError: If the new settings are not usable.
        """
        merged = None
        if config is not None:
            merged = await self._validated(integration.provider, {**integration.config, **config})
        return await self._integrations.update(integration.id, config=merged, status=status)

    async def rotate_secrets(self, integration: CrmIntegration) -> Optional[CrmIntegration]:
        """Replace both secrets (the old ones stop working at once).

        Args:
            integration (CrmIntegration): The integration.

        Returns:
            Optional[CrmIntegration]: The integration with its new secrets.
        """
        return await self._integrations.update(
            integration.id, credentials={**integration.credentials, **self._new_secrets()}
        )

    async def send_test(self, integration: CrmIntegration) -> Optional[str]:
        """Deliver an "integration.test" event right away (no queue, no retries).

        Args:
            integration (CrmIntegration): The integration to check.

        Returns:
            Optional[str]: None if the CRM accepted it, else what went wrong.
        """
        provider = self._providers.get(integration.provider)
        if provider is None:
            return f"no adapter for provider {integration.provider!r}"
        event = CrmEvent(
            id=uuid4(),
            type="integration.test",
            integration_id=integration.id,
            handoff_id=uuid4(),
            conversation_id="test",
            occurred_at=datetime.now(timezone.utc),
            data={"message": "Flowsdone test event"},
        )
        try:
            await provider.deliver(event, integration)
        except Exception as exc:
            logger.warning("crm.integration.test_failed", extra={"integration_id": str(integration.id)})
            return str(exc) or exc.__class__.__name__
        return None

    def _new_secrets(self) -> Dict[str, str]:
        """A fresh signing secret and API key.

        Returns:
            Dict[str, str]: {"signing_secret": ..., "api_key": ...}.
        """
        return {SIGNING_SECRET: self._secrets.generate(), API_KEY: self._secrets.generate()}

    async def _validated(self, provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check a provider's settings.

        Args:
            provider (str): CRM provider.
            config (Dict[str, Any]): Settings to check.

        Returns:
            Dict[str, Any]: The settings, normalized.

        Raises:
            InvalidCrmIntegrationError: If they are not usable.
        """
        if provider == "generic_webhook":
            url = str(config.get("url") or "").strip()
            if not url:
                raise InvalidCrmIntegrationError("the webhook url is required")
            try:
                await self._ensure_allowed(url)
            except Exception as exc:
                raise InvalidCrmIntegrationError(f"the webhook url is not allowed: {exc}") from exc
            return {**config, "url": url}
        raise InvalidCrmIntegrationError(f"unknown provider {provider!r}")
