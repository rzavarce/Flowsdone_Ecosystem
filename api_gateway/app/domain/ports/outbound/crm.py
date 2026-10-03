"""Ports for CRM handoffs: integrations, handoff records, the event queue
and the provider adapters that talk to each CRM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Collection, Dict, List, Optional, Protocol
from uuid import UUID

from app.domain.models.crm import CrmEvent, CrmIntegration, Handoff, HandoffCloseReason, HandoffStatus


class CrmIntegrationRepositoryPort(Protocol):
    """Storage of each project's CRM integration (credentials encrypted at rest)."""

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> CrmIntegration:
        """Create a project's integration.

        Args:
            tenant_id (UUID): Owning tenant.
            project_id (UUID): Project it belongs to.
            provider (str): CRM provider.
            config (Dict[str, Any]): Non-secret settings.
            credentials (Dict[str, Any]): Secrets.

        Returns:
            CrmIntegration: The created integration.

        Raises:
            Exception: If the project already has one (one per project).
        """
        ...

    async def get(self, integration_id: UUID) -> Optional[CrmIntegration]:
        """Fetch an integration by id.

        Args:
            integration_id (UUID): Integration id.

        Returns:
            Optional[CrmIntegration]: The integration, or None.
        """
        ...

    async def get_for_project(self, project_id: UUID) -> Optional[CrmIntegration]:
        """Fetch a project's integration, whatever its status.

        Args:
            project_id (UUID): Project id.

        Returns:
            Optional[CrmIntegration]: The integration, or None.
        """
        ...

    async def list(self, *, tenant_ids: Optional[Collection[UUID]] = None) -> List[CrmIntegration]:
        """List integrations.

        Args:
            tenant_ids (Optional[Collection[UUID]]): Only these tenants;
                None = all.

        Returns:
            List[CrmIntegration]: The integrations.
        """
        ...

    async def update(
        self,
        integration_id: UUID,
        *,
        config: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[CrmIntegration]:
        """Update an integration; omitted fields are left untouched.

        Args:
            integration_id (UUID): Integration id.
            config (Optional[Dict[str, Any]]): New settings (replaced).
            credentials (Optional[Dict[str, Any]]): New secrets (replaced).
            status (Optional[str]): New status.

        Returns:
            Optional[CrmIntegration]: The updated integration, or None.
        """
        ...

    async def delete(self, integration_id: UUID) -> bool:
        """Delete an integration.

        Args:
            integration_id (UUID): Integration id.

        Returns:
            bool: True if it existed.
        """
        ...


class HandoffRepositoryPort(Protocol):
    """Durable record of handoffs (Postgres): at most one open per conversation."""

    async def open(self, handoff: Handoff) -> Handoff:
        """Record a new open handoff, or return the one already open.

        Args:
            handoff (Handoff): The handoff to open.

        Returns:
            Handoff: The stored open handoff for that session (the
            existing one if the session already had one).
        """
        ...

    async def get_open(self, session_id: str) -> Optional[Handoff]:
        """The open handoff of a conversation, if any.

        Args:
            session_id (str): Switchboard session id.

        Returns:
            Optional[Handoff]: The open handoff, or None.
        """
        ...

    async def close(
        self, handoff_id: UUID, *, status: HandoffStatus, reason: HandoffCloseReason, at: datetime
    ) -> Optional[Handoff]:
        """End an open handoff.

        Args:
            handoff_id (UUID): Handoff id.
            status (HandoffStatus): "closed" or "expired".
            reason (HandoffCloseReason): Why it ended.
            at (datetime): When it ended.

        Returns:
            Optional[Handoff]: The ended handoff, or None if it was not
            open (already ended, or unknown).
        """
        ...


class CrmEventPublisherPort(Protocol):
    """Queues CRM events for asynchronous, retried delivery."""

    async def publish(self, event: CrmEvent) -> None:
        """Queue one event.

        Args:
            event (CrmEvent): The event to deliver.
        """
        ...


class CrmDeadLetterPort(Protocol):
    """Keeps the CRM events that could not be delivered, for inspection
    and manual replay."""

    async def publish_dead(self, event: CrmEvent, *, reason: str) -> None:
        """Park an undeliverable event.

        Args:
            event (CrmEvent): The event.
            reason (str): Why it was given up on.
        """
        ...


class CrmDeliveryError(Exception):
    """A CRM delivery failed in a way worth retrying (network, 5xx, 429)."""


class CrmProviderPort(Protocol):
    """Talks to one kind of CRM. Called by the delivery worker, never on
    the path of a channel webhook.
    """

    async def deliver(self, event: CrmEvent, integration: CrmIntegration) -> None:
        """Deliver one event to the integration's CRM.

        Args:
            event (CrmEvent): The event.
            integration (CrmIntegration): Where it goes, with its secrets.

        Raises:
            CrmDeliveryError: If the delivery failed and should be retried.
            Exception: Anything else is a permanent failure (not retried).
        """
        ...
