"""What happens to a conversation while it is handed over to a CRM, and
when its session ends under a human's watch. Used by the "crm" app
connector (every inbound message) and by the Switchboard (a new session
expires the previous handoff).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from app.domain.models.crm import CrmEvent, CrmEventType, Handoff
from app.domain.models.session import Session
from app.domain.ports.outbound import CrmEventPublisherPort, HandoffRepositoryPort

logger = logging.getLogger("crm.handoffs")


def _utcnow() -> datetime:
    """Current time, timezone-aware (UTC).

    Returns:
        datetime: Now.
    """
    return datetime.now(timezone.utc)


class CrmHandoffs:
    """Forwards a handed-over conversation's messages to the CRM and
    expires handoffs whose session ended.
    """

    def __init__(
        self,
        *,
        handoffs: HandoffRepositoryPort,
        publisher: Optional[CrmEventPublisherPort],
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        """Build the service.

        Args:
            handoffs (HandoffRepositoryPort): Handoff records.
            publisher (Optional[CrmEventPublisherPort]): The CRM event
                queue; None (no RabbitMQ) logs every event as undeliverable.
            clock (Callable[[], datetime]): Source of "now", for tests.
        """
        self._handoffs = handoffs
        self._publisher = publisher
        self._clock = clock

    async def publish(self, handoff: Handoff, event_type: CrmEventType, data: Dict[str, Any]) -> CrmEvent:
        """Queue an event about a handoff for delivery to its CRM.

        Args:
            handoff (Handoff): The handoff the event belongs to.
            event_type (CrmEventType): What happened.
            data (Dict[str, Any]): Event payload.

        Returns:
            CrmEvent: The event (queued, or only logged if there is no queue).
        """
        event = CrmEvent(
            id=uuid4(),
            type=event_type,
            integration_id=handoff.integration_id,
            handoff_id=handoff.id,
            conversation_id=handoff.session_id,
            occurred_at=self._clock(),
            data=data,
        )
        if self._publisher is None:
            logger.error("crm.event.no_queue", extra={"event_id": str(event.id), "type": event_type})
            return event
        await self._publisher.publish(event)
        return event

    async def forward_inbound(self, session: Session, text: str) -> None:
        """Send a contact's message to the CRM that owns the conversation.

        Args:
            session (Session): The conversation, currently on the "crm" app.
            text (str): The contact's message.
        """
        handoff = await self._handoffs.get_open(session.id)
        if handoff is None:
            # The session says "crm" but nothing is open (e.g. closed in a
            # race): the message is still recorded, nobody answers it.
            logger.warning("crm.handoff.missing", extra={"session_id": session.id})
            return
        await self.publish(handoff, "message.inbound", {"text": text, "contact": contact_of(session)})

    async def expire_open(self, session_id: str) -> Optional[Handoff]:
        """End the open handoff of a conversation whose session expired,
        and tell its CRM.

        Args:
            session_id (str): The conversation's session id.

        Returns:
            Optional[Handoff]: The expired handoff, or None if none was open.
        """
        handoff = await self._handoffs.get_open(session_id)
        if handoff is None:
            return None
        expired = await self._handoffs.close(handoff.id, status="expired", reason="expired", at=self._clock())
        if expired is None:
            return None
        await self.publish(expired, "handoff.expired", {})
        logger.info("crm.handoff.expired", extra={"session_id": session_id, "handoff_id": str(expired.id)})
        return expired


def contact_of(session: Session) -> Dict[str, Any]:
    """How a conversation's contact is described to the CRM.

    Args:
        session (Session): The conversation.

    Returns:
        Dict[str, Any]: Channel and the contact's ids on it.
    """
    return {
        "channel_type": session.channel_type,
        "id": session.external_conversation_key,
        "user_identifier": session.user_identifier,
    }
