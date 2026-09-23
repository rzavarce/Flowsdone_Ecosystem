"""Tests for ListProjectFlowsUseCase and ManageAgentsUseCase."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError
from app.application.use_cases.manage_agents import (
    AgentInUseError,
    FlowNotInProjectError,
    ListProjectFlowsUseCase,
    ManageAgentsUseCase,
)
from app.domain.models.agent import Agent
from app.domain.ports.outbound import LangflowFlowSummary
from api_gateway.tests.application.use_cases.test_langflow_sso import FakeLangflow, World
from api_gateway.tests.support.admin_world import InMemoryRepo
from api_gateway.tests.support.fakes import make_channel_connection

pytestmark = pytest.mark.anyio


class FlowsLangflow(FakeLangflow):
    """FakeLangflow that also lists flows per folder."""

    def __init__(self) -> None:
        super().__init__()
        self.flows_by_folder: dict = {}
        self.listed: list = []

    async def list_flows(self, access_token, folder_id):
        self.listed.append((access_token, folder_id))
        return self.flows_by_folder.get(folder_id, [])


def _setup():
    w = World()
    w.langflow = FlowsLangflow()
    w.prepare._langflow = w.langflow
    now = datetime.now(timezone.utc)
    agents = InMemoryRepo(lambda **f: Agent(id=uuid4(), status="active", created_at=now, updated_at=now, **f), "project_id")
    connections = InMemoryRepo(lambda **f: make_channel_connection(**f), "project_id")
    flows = ListProjectFlowsUseCase(project_repo=w.projects, agent_repo=agents, workspace=w.prepare, langflow=w.langflow)
    manage = ManageAgentsUseCase(agent_repo=agents, channel_connection_repo=connections, flows=flows)
    return w, agents, connections, flows, manage


async def _project_with_flows(w, *flow_ids):
    project = await w.add_project("Ventas")
    await w.prepare.open_workspace(w.tenant.id)  # creates the folder
    folder = w.accounts.folders[project.id]
    w.langflow.flows_by_folder[folder] = [LangflowFlowSummary(id=f, name=f"Flow {f}") for f in flow_ids]
    return project, folder


async def test_open_workspace_provisions_user_and_folders():
    w, *_ = _setup()
    project = await w.add_project("Soporte")

    workspace = await w.prepare.open_workspace(w.tenant.id)

    assert workspace.tokens.access_token == "access-tenant-acme"
    assert set(workspace.folders) == {project.id}


async def test_open_workspace_unknown_tenant():
    w, *_ = _setup()
    with pytest.raises(LangflowTargetNotFoundError):
        await w.prepare.open_workspace(uuid4())


async def test_lists_the_project_folder_flows_marking_registered_ones():
    w, agents, _, flows, _ = _setup()
    project, folder = await _project_with_flows(w, "f1", "f2")
    agent = await agents.create(project_id=project.id, name="A", langflow_flow_id="f2", config={}, is_default=True)

    result = await flows.execute(project.id)

    assert [(f.id, f.agent_id) for f in result] == [("f1", None), ("f2", agent.id)]
    assert w.langflow.listed[-1] == ("access-tenant-acme", folder)


async def test_listing_flows_of_an_unknown_project_fails():
    _, _, _, flows, _ = _setup()
    with pytest.raises(LangflowTargetNotFoundError):
        await flows.execute(uuid4())


async def test_create_verifies_the_flow_and_the_first_agent_is_default():
    w, agents, _, _, manage = _setup()
    project, _ = await _project_with_flows(w, "f1", "f2")

    first = await manage.create(project_id=project.id, name="Recepción", langflow_flow_id="f1")
    second = await manage.create(project_id=project.id, name="Citas", langflow_flow_id="f2")

    assert first.is_default is True and second.is_default is False
    with pytest.raises(FlowNotInProjectError):
        await manage.create(project_id=project.id, name="Otro", langflow_flow_id="ajeno")


async def test_machine_callers_may_register_any_flow():
    w, _, _, _, manage = _setup()
    project, _ = await _project_with_flows(w)

    agent = await manage.create(project_id=project.id, name="Legacy", langflow_flow_id="anywhere", verify_flow=False)

    assert agent.langflow_flow_id == "anywhere"


async def test_only_one_default_agent_per_project():
    w, agents, _, _, manage = _setup()
    project, _ = await _project_with_flows(w, "f1", "f2")
    first = await manage.create(project_id=project.id, name="A", langflow_flow_id="f1")
    second = await manage.create(project_id=project.id, name="B", langflow_flow_id="f2", is_default=True)

    assert (await agents.get_by_id(first.id)).is_default is False

    await manage.update(await agents.get_by_id(first.id), is_default=True)

    assert (await agents.get_by_id(first.id)).is_default is True
    assert (await agents.get_by_id(second.id)).is_default is False


async def test_update_verifies_only_a_changed_flow():
    w, agents, _, _, manage = _setup()
    project, _ = await _project_with_flows(w, "f1", "f2")
    agent = await manage.create(project_id=project.id, name="A", langflow_flow_id="f1")

    renamed = await manage.update(agent, name="Nuevo nombre", langflow_flow_id="f1")
    moved = await manage.update(renamed, langflow_flow_id="f2")

    assert renamed.name == "Nuevo nombre" and moved.langflow_flow_id == "f2"
    with pytest.raises(FlowNotInProjectError):
        await manage.update(moved, langflow_flow_id="ajeno")


async def test_an_agent_with_channels_cannot_be_deleted():
    w, agents, connections, _, manage = _setup()
    project, _ = await _project_with_flows(w, "f1")
    agent = await manage.create(project_id=project.id, name="A", langflow_flow_id="f1")
    connections.add(make_channel_connection(project_id=project.id, agent_id=agent.id))

    with pytest.raises(AgentInUseError) as error:
        await manage.delete(agent)
    assert error.value.channels == 1

    connections.items.clear()
    assert await manage.delete(agent) is True
