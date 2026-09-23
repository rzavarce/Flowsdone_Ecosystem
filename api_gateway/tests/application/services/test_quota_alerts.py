"""Tests for QuotaAlertMailer."""

from __future__ import annotations

import pytest

from app.application.services.quota_alerts import QuotaAlertMailer
from app.domain.models.billing import QuotaDecision
from api_gateway.tests.support.fakes import FakeEmailSender, FakeTenantBillingProfileRepo, make_tenant

pytestmark = pytest.mark.anyio


class _Tenants:
    def __init__(self, tenant):
        self.tenant = tenant

    async def get_by_id(self, tenant_id):
        return self.tenant


async def test_emails_the_billing_contact():
    tenant = make_tenant(name="Clínica Vital")
    profiles = FakeTenantBillingProfileRepo()
    await profiles.upsert(tenant.id, billing_email="facturas@vital.com")
    mailer = FakeEmailSender()
    notifier = QuotaAlertMailer(mailer=mailer, billing_profiles=profiles, tenants=_Tenants(tenant))

    await notifier.notify(
        tenant_id=tenant.id, period="2026-09", event="80",
        decision=QuotaDecision(allowed=True, reason="within_quota", channel_type="telegram", used=8, included=10),
    )

    [sent] = mailer.sent
    assert sent["to"] == "facturas@vital.com"
    assert sent["template"] == "quota_alert"
    assert sent["context"]["used"] == 8 and sent["context"]["tenant_name"] == "Clínica Vital"


async def test_without_billing_email_nothing_is_sent():
    tenant = make_tenant()
    mailer = FakeEmailSender()
    notifier = QuotaAlertMailer(mailer=mailer, billing_profiles=FakeTenantBillingProfileRepo(), tenants=_Tenants(tenant))

    await notifier.notify(
        tenant_id=tenant.id, period="2026-09", event="blocked",
        decision=QuotaDecision(allowed=False, reason="hard_stop", channel_type="telegram"),
    )

    assert mailer.sent == []
