"""Use cases of a CRM handoff: hand a conversation to the CRM, let the
CRM's agent reply, and give it back to the bot.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID, uuid4

from app.application.services.crm_handoffs import CrmHandoffs, contact_of
from app.application.services.messaging_window import MessagingWindowService
from app.application.services.switchboard import ChannelMessageNotRoutable, Switchboard
from app.application.use_cases.handle_outbound_response import HandleOutboundResponseUseCase
from app.domain.models.crm import CRM_APP, Handoff
from app.domain.models.message_envelope import MessageEnvelope, MessageMeta
from app.domain.models.messaging_window import MessagingDecision
from app.domain.ports.outbound import CrmIntegrationRepositoryPort, HandoffRepositoryPort, SessionRepositoryPort

logger = logging.getLogger("usecase.crm_handoff")


def _utcnow() -> datetime:
    """Current time, timezone-aware (UTC).

    Returns:
        datetime: Now.
    """
    return datetime.now(timezone.utc)


class HandoffNotPossibleError(Exception):
    """The conversation cannot be handed over (unknown, or its project has
    no active CRM integration)."""


class HandoffNotOpenError(Exception):
    """The conversation is not (or no longer) handed over to this integration."""


class OutsideMessagingWindowError(Exception):
    """The channel does not allow a free-form message to this contact now.

    Attributes:
        decision (MessagingDecision): What the channel would allow.
    """

    def __init__(self, decision: MessagingDecision) -> None:
        """Build the error.

        Args:
            decision (MessagingDecision): What the channel would allow.
        """
        super().__init__(f"free-form messages are not allowed now ({decision.mode})")
        self.decision = decision


class StartHandoffUseCase:
    """Hands a conversation to its project's CRM: the bot stops answering
    and the CRM receives the conversation so far.
    """

    def __init__(
        self,
        *,
        sessions: SessionRepositoryPort,
        integrations: CrmIntegrationRepositoryPort,
        handoffs: HandoffRepositoryPort,
        crm: CrmHandoffs,
        switchboard: Switchboard,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        """Build the use case.

        Args:
            sessions (SessionRepositoryPort): Live conversations.
            integrations (CrmIntegrationRepositoryPort): CRM integrations.
            handoffs (HandoffRepositoryPort): Handoff records.
            crm (CrmHandoffs): Queues the CRM events.
            switchboard (Switchboard): Moves the conversation to the "crm" app.
            clock (Callable[[], datetime]): Source of "now", for tests.
        """
        self._sessions = sessions
        self._integrations = integrations
        self._handoffs = handoffs
        self._crm = crm
        self._switchboard = switchboard
        self._clock = clock

    async def execute(self, *, session_id: str, reason: Optional[str] = None) -> Handoff:
        """Hand a conversation over (idempotent: an already open handoff is returned).

        Args:
            session_id (str): The conversation's session id.
            reason (Optional[str]): Why (shown to the agent in the CRM).

        Returns:
            Handoff: The open handoff.

        Raises:
            HandoffNotPossibleError: If the conversation does not exist or
                its project has no active CRM integration.
        """
        session = await self._sessions.get(session_id)
        if session is None:
            raise HandoffNotPossibleError(f"no conversation {session_id!r}")

        integration = await self._integrations.get_for_project(session.project_id)
        if integration is None or integration.status != "active":
            raise HandoffNotPossibleError("the project has no active CRM integration")

        existing = await self._handoffs.get_open(session_id)
        if existing is not None:
            return existing

        await self._switchboard.switch_app(session_id=session_id, to_app=CRM_APP, reason=reason or "crm_handoff")
        handoff = await self._handoffs.open(
            Handoff(
                id=uuid4(),
                session_id=session_id,
                tenant_id=session.tenant_id,
                project_id=session.project_id,
                integration_id=integration.id,
                provider=integration.provider,
                channel_type=session.channel_type,
                contact=session.external_conversation_key,
                reason=reason,
                opened_at=self._clock(),
            )
        )
        transcript = [
            {"direction": m.direction, "text": m.text, "at": m.timestamp.isoformat()} for m in session.last_messages
        ]
        await self._crm.publish(
            handoff,
            "handoff.started",
            {"reason": reason, "contact": contact_of(session), "transcript": transcript},
        )
        logger.info("crm.handoff.started", extra={"session_id": session_id, "handoff_id": str(handoff.id)})
        return handoff


class ReplyFromCrmUseCase:
    """Delivers an agent's reply, written in the CRM, to the contact."""

    def __init__(
        self,
        *,
        sessions: SessionRepositoryPort,
        handoffs: HandoffRepositoryPort,
        crm: CrmHandoffs,
        window: MessagingWindowService,
        outbound: HandleOutboundResponseUseCase,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        """Build the use case.

        Args:
            sessions (SessionRepositoryPort): Live conversations.
            handoffs (HandoffRepositoryPort): Handoff records.
            crm (CrmHandoffs): Expires a handoff whose session is gone.
            window (MessagingWindowService): The channel's messaging window.
            outbound (HandleOutboundResponseUseCase): Delivers (and
                records) the message on the conversation's channel.
            clock (Callable[[], datetime]): Source of "now", for tests.
        """
        self._sessions = sessions
        self._handoffs = handoffs
        self._crm = crm
        self._window = window
        self._outbound = outbound
        self._clock = clock

    async def execute(self, *, integration_id: UUID, conversation_id: str, text: str) -> None:
        """Send the agent's message to the contact.

        Args:
            integration_id (UUID): The CRM integration replying.
            conversation_id (str): The conversation (session) id.
            text (str): The agent's message.

        Raises:
            HandoffNotOpenError: If the conversation is not handed over to
                this integration (closed, expired, never handed over).
            OutsideMessagingWindowError: If the channel does not allow a
                free-form message to the contact now.
        """
        handoff = await self._handoffs.get_open(conversation_id)
        if handoff is None or handoff.integration_id != integration_id:
            raise HandoffNotOpenError(conversation_id)

        session = await self._sessions.get(conversation_id)
        if session is None:
            await self._crm.expire_open(conversation_id)
            raise HandoffNotOpenError(conversation_id)

        decision = await self._window.decide(
            session_id=conversation_id, channel_type=session.channel_type, now=self._clock()
        )
        if not decision.free_form_allowed:
            raise OutsideMessagingWindowError(decision)

        await self._outbound.deliver(
            MessageEnvelope(
                meta=MessageMeta(
                    message_id=str(uuid4()),
                    timestamp=self._clock(),
                    direction="outbound",
                    conversation_id=session.id,
                    channel_connection_id=str(session.channel_connection_id),
                    external_conversation_key=session.external_conversation_key,
                ),
                channel=session.channel_type,
                payload={"message": text},
            )
        )


class CloseHandoffUseCase:
    """The CRM closed the ticket: the conversation goes back to the bot."""

    def __init__(
        self,
        *,
        handoffs: HandoffRepositoryPort,
        switchboard: Switchboard,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        """Build the use case.

        Args:
            handoffs (HandoffRepositoryPort): Handoff records.
            switchboard (Switchboard): Moves the conversation back to the
                bot (its default app).
            clock (Callable[[], datetime]): Source of "now", for tests.
        """
        self._handoffs = handoffs
        self._switchboard = switchboard
        self._clock = clock

    async def execute(self, *, integration_id: UUID, conversation_id: str) -> Handoff:
        """Close the handoff and give the conversation back to the bot.

        Args:
            integration_id (UUID): The CRM integration closing it.
            conversation_id (str): The conversation (session) id.

        Returns:
            Handoff: The closed handoff.

        Raises:
            HandoffNotOpenError: If the conversation is not handed over to
                this integration.
        """
        handoff = await self._handoffs.get_open(conversation_id)
        if handoff is None or handoff.integration_id != integration_id:
            raise HandoffNotOpenError(conversation_id)

        closed = await self._handoffs.close(handoff.id, status="closed", reason="agent", at=self._clock())
        if closed is None:
            raise HandoffNotOpenError(conversation_id)

        try:
            await self._switchboard.switch_app(
                session_id=conversation_id, to_app=self._switchboard.default_app, reason="crm_handoff_closed"
            )
        except ChannelMessageNotRoutable:
            # The session already expired: the next message starts on the bot anyway.
            pass
        logger.info("crm.handoff.closed", extra={"session_id": conversation_id, "handoff_id": str(closed.id)})
        return closed
