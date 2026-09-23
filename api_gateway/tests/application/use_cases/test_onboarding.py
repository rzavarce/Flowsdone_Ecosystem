"""Tests for CreateBaseAgentUseCase and GetOnboardingStatusUseCase."""

from __future__ import annotations

import pytest

from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError
from app.application.use_cases.onboarding import CreateBaseAgentUseCase, GetOnboardingStatusUseCase
from app.domain.ports.outbound import LangflowFlowSummary, LangflowSessionError
from api_gateway.tests.application.use_cases.test_manage_agents import FlowsLangflow, _setup
from api_gateway.tests.support.fakes import (
    FakePlanRepo,
    FakeSubscriptionRepo,
    FakeTenantBillingProfileRepo,
    FakeUserRepo,
    make_channel_connection,
    make_plan,
    make_subscription,
    make_user,
)

pytestmark = pytest.mark.anyio


class OnboardingLangflow(FlowsLangflow):
    """Adds flow creation and variable names to the fake Langflow."""

    def __init__(self) -> None:
        super().__init__()
        self.created: list = []
        self.keys: dict = {}
        self.fail = False

    async def create_base_flow(self, access_token, folder_id, *, name, system_prompt):
        flow_id = f"flow-{len(self.created) + 1}"
        self.created.append({"folder": folder_id, "name": name, "prompt": system_prompt, "id": flow_id})
        self.flows_by_folder.setdefault(folder_id, []).append(LangflowFlowSummary(id=flow_id, name=name))
        return flow_id

    async def list_flows(self, access_token, folder_id):
        if self.fail:
            raise LangflowSessionError("down")
        return await super().list_flows(access_token, folder_id)

    async def llm_key_configured(self, access_token, flow_id):
        if self.fail:
            raise LangflowSessionError("down")
        return self.keys.get(flow_id, False)


def _world():
    w, agents, connections, flows, manage = _setup()
    w.langflow = OnboardingLangflow()
    w.prepare._langflow = w.langflow
    flows._langflow = w.langflow
    create = CreateBaseAgentUseCase(
        project_repo=w.projects, tenant_repo=w.tenants, workspace=w.prepare, langflow=w.langflow, manage_agents=manage
    )
    billing, users, subs, plans = FakeTenantBillingProfileRepo(), FakeUserRepo(), FakeSubscriptionRepo(), FakePlanRepo()
    status = GetOnboardingStatusUseCase(
        billing_profiles=billing, users=users, subscriptions=subs, plans=plans, project_repo=w.projects,
        agent_repo=agents, channel_connection_repo=connections, workspace=w.prepare, langflow=w.langflow,
    )
    return dict(w=w, agents=agents, connections=connections, create=create, status=status,
                billing=billing, users=users, subs=subs, plans=plans)


def _check(status, key):
    return next(c for c in status.checks if c.key == key)


async def test_base_agent_is_created_in_the_project_folder_as_default_with_the_company_prompt():
    x = _world()
    project = await x["w"].add_project("Atención")

    agent = await x["create"].execute(project_id=project.id, assistant_name="Fibi", tone="profesional", instructions="Fibra óptica.")

    [created] = x["w"].langflow.created
    assert created["folder"] == x["w"].accounts.folders[project.id]
    assert created["prompt"].startswith("Eres Fibi, el asistente virtual de Acme.")
    assert "Fibra óptica." in created["prompt"]
    assert agent.langflow_flow_id == created["id"] and agent.is_default and agent.name == "Fibi"


async def test_base_agent_for_an_unknown_project():
    from uuid import uuid4

    x = _world()
    with pytest.raises(LangflowTargetNotFoundError):
        await x["create"].execute(project_id=uuid4(), assistant_name="A", tone="cercano", instructions="")


async def test_a_new_tenant_starts_at_the_company_step_with_everything_missing():
    x = _world()

    status = await x["status"].execute(x["w"].tenant.id)

    assert status.next_step == "company" and status.project_id is None
    assert {c.key: c.status for c in status.checks} == {
        "billing": "missing", "client_account": "missing", "plan": "missing", "project": "missing",
        "agent": "missing", "openai_key": "missing", "channel": "warning",
    }


async def test_the_wizard_resumes_at_each_missing_step_and_ends_in_summary():
    x = _world()
    tenant = x["w"].tenant
    await x["billing"].upsert(tenant.id, billing_email="f@acme.com", legal_name="Acme SL")
    assert (await x["status"].execute(tenant.id)).next_step == "plan"

    plan = await x["plans"].create(make_plan(name="Pro"))
    await x["subs"].upsert(make_subscription(tenant_id=tenant.id, plan_id=plan.id))
    assert (await x["status"].execute(tenant.id)).next_step == "project"

    project = await x["w"].add_project("Atención")
    assert (await x["status"].execute(tenant.id)).next_step == "agent"

    await x["create"].execute(project_id=project.id, assistant_name="Fibi", tone="cercano", instructions="")
    x["users"].add(make_user(role="client", status="pending", tenant_ids=[tenant.id]))
    x["w"].langflow.keys = {f["id"]: True for f in x["w"].langflow.created}  # key set in the editor
    x["connections"].add(make_channel_connection(project_id=project.id))

    status = await x["status"].execute(tenant.id)

    assert status.next_step == "summary" and status.project_id == project.id
    assert _check(status, "billing").detail == "Acme SL"
    assert _check(status, "plan").detail == "Pro"
    assert (_check(status, "client_account").status, _check(status, "client_account").detail) == ("warning", "pending")
    assert _check(status, "agent").status == "ok" and _check(status, "openai_key").status == "ok"
    assert _check(status, "channel").status == "ok"


async def test_a_base_agent_without_api_key_is_flagged():
    x = _world()
    project = await x["w"].add_project("Atención")
    await x["create"].execute(project_id=project.id, assistant_name="Fibi", tone="cercano", instructions="")

    status = await x["status"].execute(x["w"].tenant.id)

    assert _check(status, "agent").status == "ok" and _check(status, "openai_key").status == "missing"


async def test_an_agent_whose_flow_is_gone_is_a_warning_and_langflow_down_is_unknown():
    x = _world()
    project = await x["w"].add_project("Atención")
    await x["create"].execute(project_id=project.id, assistant_name="Fibi", tone="cercano", instructions="")
    x["w"].langflow.flows_by_folder.clear()

    assert _check(await x["status"].execute(x["w"].tenant.id), "agent").status == "warning"

    x["w"].langflow.fail = True
    status = await x["status"].execute(x["w"].tenant.id)
    assert _check(status, "agent").status == "unknown" and _check(status, "openai_key").status == "unknown"
