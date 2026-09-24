"""Use cases for registering the Langflow flows of a project as agents.

An agent is the gateway's record that ties a project to one Langflow flow
(`langflow_flow_id`): channels are connected to agents, and every inbound
message runs the flow of its channel's agent. The flow itself lives in the
tenant's Langflow, in the folder that mirrors the project (see
`langflow_sso.py`); the console lists that folder so the flow is picked,
never typed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError, PrepareLangflowSessionUseCase
from app.domain.models.agent import Agent
from app.domain.ports.outbound import (
    AgentRepositoryPort,
    AlreadyExistsError,
    ChannelConnectionRepositoryPort,
    LangflowAdminPort,
    LangflowSessionError,
    ProjectRepositoryPort,
)


class FlowNotInProjectError(Exception):
    """The flow is not in the project's Langflow folder (maps to 400)."""


class AgentInUseError(Exception):
    """The agent still has channels connected (maps to 409).

    Attributes:
        channels (int): How many channel connections use it.
    """

    def __init__(self, channels: int) -> None:
        """Build the error.

        Args:
            channels (int): How many channel connections use the agent.
        """
        super().__init__(f"agent has {channels} channel connection(s)")
        self.channels = channels


@dataclass(frozen=True)
class ProjectFlow:
    """A flow in a project's Langflow folder.

    Attributes:
        id (str): Langflow flow id.
        name (str): Flow name.
        description (Optional[str]): Flow description.
        agent_id (Optional[UUID]): The agent already registered for it in
            this project, if any.
    """

    id: str
    name: str
    description: Optional[str]
    agent_id: Optional[UUID]


class ListProjectFlowsUseCase:
    """Lists the flows in a project's Langflow folder, marking which ones
    are already registered as agents of the project. Flows of the project's
    agents that live in the tenant's default folder (the base agent's) are
    included too."""

    def __init__(
        self,
        *,
        project_repo: ProjectRepositoryPort,
        agent_repo: AgentRepositoryPort,
        workspace: PrepareLangflowSessionUseCase,
        langflow: LangflowAdminPort,
    ) -> None:
        """Build the use case.

        Args:
            project_repo (ProjectRepositoryPort): Resolves the project's tenant.
            agent_repo (AgentRepositoryPort): The project's registered agents.
            workspace (PrepareLangflowSessionUseCase): Opens the tenant's
                Langflow (provisioning its user and folders if needed).
            langflow (LangflowAdminPort): Lists the folder's flows.
        """
        self._projects = project_repo
        self._agents = agent_repo
        self._workspace = workspace
        self._langflow = langflow

    async def execute(self, project_id: UUID) -> List[ProjectFlow]:
        """List the project's flows.

        Args:
            project_id (UUID): The project.

        Returns:
            List[ProjectFlow]: Its flows, by name.

        Raises:
            LangflowTargetNotFoundError: If the project (or its tenant) does not exist.
            LangflowSessionError: If Langflow fails.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise LangflowTargetNotFoundError("project not found")
        workspace = await self._workspace.open_workspace(project.tenant_id)
        folder_id = workspace.folders.get(project_id)
        if folder_id is None:
            return []
        token = workspace.tokens.access_token
        registered = {a.langflow_flow_id: a.id for a in await self._agents.list_by_project(project_id)}
        flows = await self._langflow.list_flows(token, folder_id)
        # The base agent's flow lives in the default folder ("Starter
        # Project"): list it too, but only the ones registered for this project.
        in_folder = {f.id for f in flows}
        if any(flow_id not in in_folder for flow_id in registered):
            default = await self._langflow.list_flows(token, await self._langflow.default_folder(token))
            flows += [f for f in default if f.id in registered and f.id not in in_folder]
        return [
            ProjectFlow(id=f.id, name=f.name, description=f.description, agent_id=registered.get(f.id))
            for f in sorted(flows, key=lambda f: f.name.lower())
        ]

    async def rename(self, project_id: UUID, flow_id: str, name: str) -> None:
        """Rename one of the project's flows in its tenant's Langflow.

        Args:
            project_id (UUID): The project.
            flow_id (str): The flow.
            name (str): Its new name.

        Raises:
            LangflowTargetNotFoundError: If the project (or its tenant) does not exist.
            AlreadyExistsError: If the tenant already has a flow with that name.
            LangflowSessionError: If Langflow fails.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            raise LangflowTargetNotFoundError("project not found")
        workspace = await self._workspace.open_workspace(project.tenant_id)
        await self._langflow.rename_flow(workspace.tokens.access_token, flow_id, name)


class ManageAgentsUseCase:
    """Create, edit and delete a project's agents with the rules the plain
    repository does not enforce:

    - a flow picked in the console must be in the project's Langflow folder
      (so nobody points an agent at another tenant's flow, or at a flow id
      that does not exist and would fail on every message);
    - a project has at most one default agent;
    - an agent with channels connected cannot be deleted.
    """

    def __init__(
        self,
        *,
        agent_repo: AgentRepositoryPort,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        flows: ListProjectFlowsUseCase,
    ) -> None:
        """Build the use case.

        Args:
            agent_repo (AgentRepositoryPort): Agents.
            channel_connection_repo (ChannelConnectionRepositoryPort): To
                know whether an agent has channels.
            flows (ListProjectFlowsUseCase): The project's Langflow flows.
        """
        self._agents = agent_repo
        self._channels = channel_connection_repo
        self._flows = flows

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        langflow_flow_id: str,
        config: Optional[Dict[str, Any]] = None,
        is_default: bool = False,
        verify_flow: bool = True,
    ) -> Agent:
        """Register a flow of the project as an agent.

        The project's first agent is always its default one.

        Args:
            project_id (UUID): The project.
            name (str): Display name.
            langflow_flow_id (str): The flow.
            config (Optional[Dict[str, Any]]): Free-form agent configuration.
            is_default (bool): Make it the project's default agent.
            verify_flow (bool): Check the flow is in the project's folder.
                False only for machine callers (API key, onboarding agent)
                whose flows may live outside the tenant folders.

        Returns:
            Agent: The new agent.

        Raises:
            FlowNotInProjectError: If `verify_flow` and the flow is not there.
            AlreadyExistsError: If the project has an agent with that name.
            LangflowSessionError: If Langflow fails while verifying.
        """
        if verify_flow:
            await self._require_flow(project_id, langflow_flow_id)
        siblings = await self._agents.list_by_project(project_id)
        make_default = is_default or not siblings
        agent = await self._agents.create(
            project_id=project_id,
            name=name,
            langflow_flow_id=langflow_flow_id,
            config=config or {},
            is_default=make_default,
        )
        if make_default:
            await self._clear_other_defaults(agent)
        return agent

    async def update(self, agent: Agent, *, verify_flow: bool = True, **fields: Any) -> Optional[Agent]:
        """Edit an agent.

        A new name is also given to its flow in Langflow, so the console and
        the editor show the same one. If Langflow refuses it, the agent is
        left as it was.

        Args:
            agent (Agent): The agent as it is now.
            verify_flow (bool): Check a new flow is in the project's folder
                (and rename the flow along with the agent). False only for
                machine callers, whose flows may live outside the tenant folders.
            **fields (Any): Fields to change (unset ones are not passed).

        Returns:
            Optional[Agent]: The updated agent, or None if it vanished.

        Raises:
            FlowNotInProjectError: If the new flow is not in the folder.
            AlreadyExistsError: If the new name is taken in the project, or
                by another flow of the tenant in Langflow.
            LangflowSessionError: If Langflow fails.
        """
        new_flow = fields.get("langflow_flow_id")
        if verify_flow and new_flow and new_flow != agent.langflow_flow_id:
            await self._require_flow(agent.project_id, new_flow)
        updated = await self._agents.update(agent.id, **fields)
        new_name = fields.get("name")
        if updated is not None and verify_flow and new_name and new_name != agent.name:
            try:
                await self._flows.rename(agent.project_id, updated.langflow_flow_id, new_name)
            except (AlreadyExistsError, LangflowSessionError, LangflowTargetNotFoundError):
                await self._agents.update(agent.id, **{key: getattr(agent, key) for key in fields})
                raise
        if updated is not None and fields.get("is_default"):
            await self._clear_other_defaults(updated)
        return updated

    async def delete(self, agent: Agent) -> bool:
        """Delete an agent that has no channels connected.

        Args:
            agent (Agent): The agent.

        Returns:
            bool: True if it was deleted.

        Raises:
            AgentInUseError: If channels are still connected to it.
        """
        in_use = [c for c in await self._channels.list_by_project(agent.project_id) if c.agent_id == agent.id]
        if in_use:
            raise AgentInUseError(len(in_use))
        return await self._agents.delete(agent.id)

    async def _require_flow(self, project_id: UUID, flow_id: str) -> None:
        """Fail unless the flow is in the project's Langflow folder.

        Args:
            project_id (UUID): The project.
            flow_id (str): The flow.

        Raises:
            FlowNotInProjectError: If it is not.
        """
        if not any(f.id == flow_id for f in await self._flows.execute(project_id)):
            raise FlowNotInProjectError(f"flow {flow_id} is not in the project's Langflow folder")

    async def _clear_other_defaults(self, agent: Agent) -> None:
        """Make `agent` the only default agent of its project.

        Args:
            agent (Agent): The new default agent.
        """
        for other in await self._agents.list_by_project(agent.project_id):
            if other.id != agent.id and other.is_default:
                await self._agents.update(other.id, is_default=False)
