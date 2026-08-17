"""Port for a destination "app" a conversation can be switched to
(Strategy) - Langflow today, a ticketing system/another bot/email in
the future. Switchboard depends only on this interface, never on a
concrete app's SDK.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol

from app.domain.models.session import Session


class AppTurnResult:
    """Result of a synchronous AppConnectorPort.handle_turn() call.

    Only relevant for connectors that can answer immediately (e.g. a
    quick ticket-created acknowledgement); Langflow's connector never
    returns this - its response arrives later through the existing
    Kafka pipeline, and Switchboard does not wait for it.

    Attributes:
        text (str): Text to deliver back to the caller right away.
    """

    def __init__(self, text: str) -> None:
        self.text = text


class AppConnectorPort(Protocol):
    """Strategy for a single destination app. Implementations own
    everything specific to talking to that app (transport, auth,
    payload shape) - Switchboard and Session never know those details.
    """

    app_name: str

    async def handle_turn(
        self,
        *,
        session: Session,
        message_text: str,
        raw_payload: Dict[str, Any],
    ) -> Optional[AppTurnResult]:
        """Process one inbound turn for a session currently assigned to
        this app.

        May mutate `session.variables` in place - Switchboard persists
        the session again right after this call, so any mutation here
        is picked up automatically.

        Args:
            session (Session): The conversation's current state.
            message_text (str): The caller's message for this turn.
            raw_payload (Dict[str, Any]): The raw, channel-specific
                payload, kept for connectors that need more than the
                plain text.

        Returns:
            Optional[AppTurnResult]: A result to deliver immediately,
            if this connector can answer synchronously; None if it
            will deliver the response later through its own means
            (e.g. Langflow's async Kafka pipeline).
        """
        ...
