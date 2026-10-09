"""Tells what may be sent to a contact right now, given the channel's
messaging window and when the contact last wrote.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.domain.models.messaging_window import MessagingDecision, MessagingWindowPolicy
from app.domain.ports.outbound import ConversationRepositoryPort


class MessagingWindowService:
    """Combines MessagingWindowPolicy with the contact's last inbound
    message, for anything that sends on its own initiative (an agent's
    reply from a CRM, a scheduled journey step) rather than as the
    immediate answer to an inbound message.
    """

    def __init__(
        self,
        *,
        conversations: ConversationRepositoryPort,
        policy: Optional[MessagingWindowPolicy] = None,
    ) -> None:
        """Build the service.

        Args:
            conversations (ConversationRepositoryPort): Source of the
                contact's last inbound message time.
            policy (Optional[MessagingWindowPolicy]): The window rules;
                the standard 24h policy if omitted.
        """
        self._conversations = conversations
        self._policy = policy or MessagingWindowPolicy()

    async def decide(
        self, *, session_id: str, channel_type: str, now: Optional[datetime] = None
    ) -> MessagingDecision:
        """What may be sent to the contact of a session right now.

        Args:
            session_id (str): Switchboard session id of the contact.
            channel_type (str): The channel the message would go out on.
            now (Optional[datetime]): The current time; defaults to now (UTC).

        Returns:
            MessagingDecision: The allowed mode and when the window closes.
        """
        last_inbound_at = await self._conversations.last_inbound_at(session_id)
        return self._policy.decide(
            channel_type=channel_type,
            last_inbound_at=last_inbound_at,
            now=now or datetime.now(timezone.utc),
        )
