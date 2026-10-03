"""Delivers one queued CRM event to its CRM, retrying transient failures."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Literal, Optional

from app.domain.models.crm import CrmEvent
from app.domain.ports.outbound import (
    CrmDeadLetterPort,
    CrmDeliveryError,
    CrmIntegrationRepositoryPort,
    CrmProviderPort,
)

logger = logging.getLogger("usecase.deliver_crm_event")

DeliveryOutcome = Literal["delivered", "dropped", "dead"]


class DeliverCrmEventUseCase:
    """Hands an event to its integration's provider adapter.

    Transient failures (CrmDeliveryError) are retried with exponential
    backoff; a permanent failure, or running out of attempts, parks the
    event in the dead-letter queue. Events of a deleted or inactive
    integration are dropped.
    """

    def __init__(
        self,
        *,
        integrations: CrmIntegrationRepositoryPort,
        providers: Dict[str, CrmProviderPort],
        dead_letters: Optional[CrmDeadLetterPort],
        max_attempts: int,
        backoff_seconds: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Build the use case.

        Args:
            integrations (CrmIntegrationRepositoryPort): Where each event goes.
            providers (Dict[str, CrmProviderPort]): Adapter per provider.
            dead_letters (Optional[CrmDeadLetterPort]): Where failed events
                are parked; None only logs them.
            max_attempts (int): Attempts before giving up (>= 1).
            backoff_seconds (float): Wait before the 2nd attempt; doubles
                after each failure.
            sleep (Callable[[float], Awaitable[None]]): Waiting, for tests.
        """
        self._integrations = integrations
        self._providers = providers
        self._dead_letters = dead_letters
        self._max_attempts = max(1, max_attempts)
        self._backoff = backoff_seconds
        self._sleep = sleep

    async def execute(self, event: CrmEvent) -> DeliveryOutcome:
        """Deliver one event.

        Args:
            event (CrmEvent): The event.

        Returns:
            DeliveryOutcome: "delivered", "dropped" (no active integration)
            or "dead" (parked after failing).
        """
        integration = await self._integrations.get(event.integration_id)
        if integration is None or integration.status != "active":
            logger.warning("crm.event.dropped", extra={"event_id": str(event.id), "type": event.type})
            return "dropped"

        provider = self._providers.get(integration.provider)
        if provider is None:
            return await self._dead(event, f"no adapter for provider {integration.provider!r}")

        for attempt in range(1, self._max_attempts + 1):
            try:
                await provider.deliver(event, integration)
            except CrmDeliveryError as exc:
                logger.warning(
                    "crm.event.retry",
                    extra={"event_id": str(event.id), "attempt": attempt, "error": str(exc)},
                )
                if attempt == self._max_attempts:
                    return await self._dead(event, f"gave up after {attempt} attempts: {exc}")
                await self._sleep(self._backoff * 2 ** (attempt - 1))
            except Exception as exc:
                return await self._dead(event, f"permanent failure: {exc}")
            else:
                logger.info("crm.event.delivered", extra={"event_id": str(event.id), "type": event.type, "attempt": attempt})
                return "delivered"
        return await self._dead(event, "no attempts made")  # unreachable: max_attempts >= 1

    async def _dead(self, event: CrmEvent, reason: str) -> DeliveryOutcome:
        """Park an event that could not be delivered.

        Args:
            event (CrmEvent): The event.
            reason (str): Why.

        Returns:
            DeliveryOutcome: "dead".
        """
        logger.error("crm.event.dead", extra={"event_id": str(event.id), "type": event.type, "reason": reason})
        if self._dead_letters is not None:
            await self._dead_letters.publish_dead(event, reason=reason)
        return "dead"
