"""Factory that assembles all available app connectors."""

from __future__ import annotations

from typing import Any, Dict

from ....domain.ports.outbound import AppConnectorPort
from .langflow_app_connector import LangflowAppConnector


class AppConnectorFactory:
    """Builds the app_name -> AppConnectorPort map Switchboard dispatches
    turns through.

    Adding a future destination app (Zendesk, Jira, Salesforce, email,
    another bot) is one more entry here, built from whatever
    ports/clients it needs - Switchboard never changes.
    """

    def build_all(self, *, ingest_message_use_case: Any) -> Dict[str, AppConnectorPort]:
        """Instantiate every supported app connector.

        Args:
            ingest_message_use_case (Any): Forwarded to LangflowAppConnector.

        Returns:
            Dict[str, AppConnectorPort]: A dict mapping each supported
            app_name to its connector.
        """
        return {
            "langflow": LangflowAppConnector(ingest_message_use_case),
        }
