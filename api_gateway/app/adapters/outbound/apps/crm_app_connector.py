"""AppConnector for conversations handed over to a CRM."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.application.services.crm_handoffs import CrmHandoffs
from app.domain.models.crm import CRM_APP
from app.domain.models.session import Session
from app.domain.ports.outbound.app_connector import AppTurnResult


class CrmAppConnector:
    """The "crm" destination app: the bot is silent and every message from
    the contact goes to the CRM's agent (asynchronously, through the CRM
    event queue); the agent's replies come back through the CRM API.
    """

    app_name = CRM_APP

    def __init__(self, crm_handoffs: CrmHandoffs) -> None:
        """Build the connector.

        Args:
            crm_handoffs (CrmHandoffs): Forwards the messages to the CRM.
        """
        self._crm = crm_handoffs

    async def handle_turn(
        self, *, session: Session, message_text: str, raw_payload: Dict[str, Any]
    ) -> Optional[AppTurnResult]:
        """Forward the contact's message to the CRM; nothing to answer now.

        Args:
            session (Session): The handed-over conversation.
            message_text (str): The contact's message.
            raw_payload (Dict[str, Any]): Unused.

        Returns:
            Optional[AppTurnResult]: Always None - the agent replies later.
        """
        await self._crm.forward_inbound(session, message_text)
        return None
