"""Tests for GetOverviewDashboardUseCase (dashboard per profile, tenant lock)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.auth_dto import AuthenticatedUser, TenantRef
from app.application.use_cases.analytics_dashboards import (
    GetOverviewDashboardUseCase,
    NoTenantsError,
    TenantOutOfScopeError,
)

pytestmark = pytest.mark.anyio

T1, T2, T3 = uuid4(), uuid4(), uuid4()


class FakeEmbeds:
    def __init__(self) -> None:
        self.calls: list = []

    async def embed_url(self, dashboard_key, *, tenant_ids, ttl_seconds):
        self.calls.append((dashboard_key, list(tenant_ids), ttl_seconds))
        return f"https://bi/embed/{dashboard_key}"


def _user(role, *tenant_ids):
    return AuthenticatedUser(id=uuid4(), email="u@x.com", name="U", role=role,
                             tenants=[TenantRef(id=t, name=str(t)) for t in tenant_ids])


def _use_case():
    embeds = FakeEmbeds()
    return GetOverviewDashboardUseCase(embeds=embeds, ttl_seconds=600), embeds


@pytest.mark.parametrize("role,dashboard", [
    ("admin", "platform_admin"), ("tenant_manager", "platform"), ("botmaster", "platform"),
    ("client", "client"), ("consultant", "client"),
])
async def test_each_profile_gets_its_dashboard(role, dashboard):
    use_case, embeds = _use_case()
    result = await use_case.execute(_user(role, T1))
    assert result.dashboard == dashboard and result.url.endswith(dashboard) and result.expires_in == 600
    assert embeds.calls[0][2] == 600


async def test_without_a_chosen_tenant_admins_see_all_and_the_rest_their_own():
    use_case, embeds = _use_case()
    await use_case.execute(_user("admin", T1, T2, T3))
    await use_case.execute(_user("tenant_manager", T1, T2))
    await use_case.execute(_user("client", T3))
    assert [c[1] for c in embeds.calls] == [[], [str(T1), str(T2)], [str(T3)]]


async def test_a_chosen_tenant_must_be_one_of_the_users():
    use_case, embeds = _use_case()
    await use_case.execute(_user("tenant_manager", T1, T2), T2)
    assert embeds.calls[-1][1] == [str(T2)]

    for role in ("tenant_manager", "client", "admin"):
        with pytest.raises(TenantOutOfScopeError):
            await use_case.execute(_user(role, T1), T3)
    assert len(embeds.calls) == 1  # nothing signed for a foreign tenant


async def test_staff_without_tenants_see_nothing_instead_of_everything():
    use_case, embeds = _use_case()
    for role in ("tenant_manager", "botmaster", "client"):
        with pytest.raises(NoTenantsError):
            await use_case.execute(_user(role))
    assert embeds.calls == []


def _reports():
    from app.application.use_cases.analytics_dashboards import ReportsUseCase

    embeds = FakeEmbeds()
    return ReportsUseCase(embeds=embeds, ttl_seconds=600), embeds


def test_reports_are_for_admins_managers_and_the_client_side_only():
    from app.application.use_cases.analytics_dashboards import REPORT_KEYS

    use_case, _ = _reports()
    for role in ("admin", "tenant_manager", "client", "consultant"):
        assert use_case.available(_user(role, T1)) == list(REPORT_KEYS)
    assert use_case.available(_user("botmaster", T1)) == []


async def test_a_report_follows_the_same_tenant_rules_as_the_dashboard():
    from app.application.use_cases.analytics_dashboards import ReportNotFoundError

    use_case, embeds = _reports()
    result = await use_case.open(_user("client", T1), "report_hours")
    await use_case.open(_user("admin", T1, T2), "report_usage")
    await use_case.open(_user("tenant_manager", T1, T2), "report_agents", T2)
    assert result.dashboard == "report_hours" and result.expires_in == 600
    assert [c[:2] for c in embeds.calls] == [("report_hours", [str(T1)]), ("report_usage", []), ("report_agents", [str(T2)])]

    with pytest.raises(TenantOutOfScopeError):
        await use_case.open(_user("client", T1), "report_hours", T3)
    with pytest.raises(ReportNotFoundError):
        await use_case.open(_user("botmaster", T1), "report_hours")
    with pytest.raises(ReportNotFoundError):
        await use_case.open(_user("admin", T1), "platform_admin")  # dashboards are not reports
    assert len(embeds.calls) == 3
