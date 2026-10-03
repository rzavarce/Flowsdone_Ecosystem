"""Factory that assembles all available app connectors."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.domain.ports.outbound import AppConnectorPort
from app.adapters.outbound.apps.crm_app_connector import CrmAppConnector
from app.adapters.outbound.apps.langflow_app_connector import LangflowAppConnector
from app.application.services.crm_handoffs import CrmHandoffs


class AppConnectorFactory:
    """Builds the app_name -> AppConnectorPort map Switchboard dispatches
    turns through.

    Adding a future destination app (Zendesk, Jira, Salesforce, email,
    another bot) is one more entry here, built from whatever
    ports/clients it needs - Switchboard never changes.
    """

    def build_all(
        self, *, ingest_message_use_case: Any, crm_handoffs: Optional[CrmHandoffs] = None
    ) -> Dict[str, AppConnectorPort]:
        """Instantiate every supported app connector.

        Args:
            ingest_message_use_case (Any): Forwarded to LangflowAppConnector.
            crm_handoffs (Optional[CrmHandoffs]): Enables the "crm" app
                (conversations handed over to a CRM).

        Returns:
            Dict[str, AppConnectorPort]: A dict mapping each supported
            app_name to its connector.
        """
        connectors: Dict[str, AppConnectorPort] = {
            "langflow": LangflowAppConnector(ingest_message_use_case),
        }
        if crm_handoffs is not None:
            connectors["crm"] = CrmAppConnector(crm_handoffs)
        return connectors
