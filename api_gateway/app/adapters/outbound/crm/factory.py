"""Factory that assembles the CRM provider adapters."""

from __future__ import annotations

from typing import Awaitable, Callable, Dict

from app.adapters.outbound.crm.generic_webhook import GenericWebhookProvider
from app.domain.ports.outbound import CrmProviderPort


class CrmProviderFactory:
    """Builds the provider -> CrmProviderPort map the CRM worker delivers
    through. Adding a CRM (Zendesk, Salesforce...) is one more entry.
    """

    def build_all(self, *, ensure_allowed: Callable[[str], Awaitable[None]]) -> Dict[str, CrmProviderPort]:
        """Instantiate every supported CRM provider.

        Args:
            ensure_allowed (Callable[[str], Awaitable[None]]): Outbound URL
                guard shared with the workflow callbacks.

        Returns:
            Dict[str, CrmProviderPort]: Provider name -> adapter.
        """
        return {"generic_webhook": GenericWebhookProvider(ensure_allowed=ensure_allowed)}
