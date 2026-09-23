"""Emails quota alerts to the tenant's billing contact."""

from __future__ import annotations

import logging
from uuid import UUID

from app.domain.models.billing import QuotaDecision
from app.domain.ports.outbound import (
    EmailSenderPort,
    TenantBillingProfileRepositoryPort,
    TenantRepositoryPort,
)

logger = logging.getLogger("billing.quota_alerts")

_SUBJECTS = {
    "80": "Flowsdone: has usado el 80% de los mensajes de tu plan",
    "100": "Flowsdone: has alcanzado los mensajes incluidos en tu plan",
    "blocked": "Flowsdone: tu asistente ha dejado de responder por el límite del plan",
}


class QuotaAlertMailer:
    """QuotaAlertNotifier that emails the tenant's billing address
    (template quota_alert). Tenants without one only get a log line.
    """

    def __init__(
        self,
        *,
        mailer: EmailSenderPort,
        billing_profiles: TenantBillingProfileRepositoryPort,
        tenants: TenantRepositoryPort,
    ) -> None:
        """Build the notifier.

        Args:
            mailer (EmailSenderPort): Sends the email.
            billing_profiles (TenantBillingProfileRepositoryPort): Where the
                billing email is read from.
            tenants (TenantRepositoryPort): For the tenant's name.
        """
        self._mailer = mailer
        self._profiles = billing_profiles
        self._tenants = tenants

    async def notify(self, *, tenant_id: UUID, period: str, decision: QuotaDecision, event: str) -> None:
        """Email one alert.

        Args:
            tenant_id (UUID): Tenant id.
            period (str): "YYYY-MM".
            decision (QuotaDecision): The triggering decision.
            event (str): "80", "100" or "blocked".
        """
        logger.warning(
            "billing.quota.alert",
            extra={
                "tenant_id": str(tenant_id),
                "period": period,
                "channel_type": decision.channel_type,
                "event": event,
                "used": decision.used,
                "included": decision.included,
            },
        )
        profile = await self._profiles.get_by_tenant_id(tenant_id)
        if profile is None or not profile.billing_email:
            return
        tenant = await self._tenants.get_by_id(tenant_id)
        await self._mailer.send_template(
            to=profile.billing_email,
            template="quota_alert",
            subject=_SUBJECTS.get(event, _SUBJECTS["100"]),
            context={
                "tenant_name": tenant.name if tenant else "",
                "event": event,
                "channel": decision.channel_type,
                "used": decision.used,
                "included": decision.included,
                "period": period,
                "reason": decision.reason,
            },
        )
