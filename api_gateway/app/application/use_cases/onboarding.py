"""Use cases behind the new-client wizard: the base agent, and the
onboarding status (the checklist the wizard resumes from and the tenant
screen shows).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Literal, Optional
from uuid import UUID

from app.application.use_cases.langflow_sso import LangflowTargetNotFoundError, PrepareLangflowSessionUseCase
from app.application.use_cases.manage_agents import ManageAgentsUseCase
from app.domain.models.agent import Agent
from app.domain.models.base_agent import AgentTone, BaseAgentSpec, build_system_prompt
from app.domain.ports.outbound import (
    AgentRepositoryPort,
    ChannelConnectionRepositoryPort,
    LangflowAdminPort,
    LangflowSessionError,
    PlanRepositoryPort,
    ProjectRepositoryPort,
    SubscriptionRepositoryPort,
    TenantBillingProfileRepositoryPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

logger = logging.getLogger("usecase.onboarding")

CheckStatus = Literal["ok", "warning", "missing", "unknown"]
WizardStep = Literal["company", "plan", "project", "agent", "summary"]


class CreateBaseAgentUseCase:
    """Creates a project's base agent: a chat flow with conversation
    memory and a system prompt built from the wizard's answers, in the
    project's Langflow folder, registered as the project's default agent.
    """

    def __init__(
        self,
        *,
        project_repo: ProjectRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        workspace: PrepareLangflowSessionUseCase,
        langflow: LangflowAdminPort,
        manage_agents: ManageAgentsUseCase,
    ) -> None:
        """Build the use case.

        Args:
            project_repo (ProjectRepositoryPort): Resolves the project.
            tenant_repo (TenantRepositoryPort): The company name for the prompt.
            workspace (PrepareLangflowSessionUseCase): Opens the tenant's Langflow.
            langflow (LangflowAdminPort): Creates the flow.
            manage_agents (ManageAgentsUseCase): Registers the agent.
        """
        self._projects = project_repo
        self._tenants = tenant_repo
        self._workspace = workspace
        self._langflow = langflow
        self._agents = manage_agents

    async def execute(
        self, *, project_id: UUID, assistant_name: str, tone: AgentTone, instructions: str
    ) -> Agent:
        """Create the flow and register it.

        Args:
            project_id (UUID): The project.
            assistant_name (str): Name the assistant introduces itself with.
            tone (AgentTone): How it talks.
            instructions (str): About the business and how to attend.

        Returns:
            Agent: The new default agent.

        Raises:
            LangflowTargetNotFoundError: If the project or its tenant does not exist.
            LangflowSessionError: If Langflow fails.
            AlreadyExistsError: If the project already has an agent with that name.
        """
        project = await self._projects.get_by_id(project_id)
        tenant = await self._tenants.get_by_id(project.tenant_id) if project else None
        if project is None or tenant is None:
            raise LangflowTargetNotFoundError("project not found")
        spec = BaseAgentSpec(
            assistant_name=assistant_name, company_name=tenant.name, tone=tone, instructions=instructions
        )
        workspace = await self._workspace.open_workspace(tenant.id)
        flow_id = await self._langflow.create_base_flow(
            workspace.tokens.access_token,
            workspace.folders[project_id],
            name=spec.assistant_name,
            system_prompt=build_system_prompt(spec),
        )
        logger.info("onboarding.base_agent.flow_created", extra={"project_id": str(project_id), "flow_id": flow_id})
        # Just created in the project's folder: no need to list it back.
        return await self._agents.create(
            project_id=project_id, name=spec.assistant_name, langflow_flow_id=flow_id, is_default=True, verify_flow=False
        )


@dataclass(frozen=True)
class OnboardingCheck:
    """One item of the onboarding checklist.

    Attributes:
        key (str): Stable id ("billing", "client_account", "plan"...).
        status (CheckStatus): ok / warning / missing / unknown.
        detail (Optional[str]): What was found (plan name, user status...).
    """

    key: str
    status: CheckStatus
    detail: Optional[str] = None


@dataclass(frozen=True)
class OnboardingStatus:
    """Where a tenant's onboarding stands.

    Attributes:
        tenant_id (UUID): The tenant.
        next_step (WizardStep): First wizard step still to do ("summary"
            when the four wizard steps are done).
        project_id (Optional[UUID]): The project the wizard works on (the
            first one, by name).
        checks (List[OnboardingCheck]): The checklist.
    """

    tenant_id: UUID
    next_step: WizardStep
    project_id: Optional[UUID]
    checks: List[OnboardingCheck] = field(default_factory=list)


class GetOnboardingStatusUseCase:
    """Computes the onboarding checklist of a tenant from what actually
    exists (never from a stored wizard state, so it cannot drift), which
    also tells the wizard where to resume.
    """

    def __init__(
        self,
        *,
        billing_profiles: TenantBillingProfileRepositoryPort,
        users: UserRepositoryPort,
        subscriptions: SubscriptionRepositoryPort,
        plans: PlanRepositoryPort,
        project_repo: ProjectRepositoryPort,
        agent_repo: AgentRepositoryPort,
        channel_connection_repo: ChannelConnectionRepositoryPort,
        workspace: PrepareLangflowSessionUseCase,
        langflow: LangflowAdminPort,
    ) -> None:
        """Build the use case.

        Args:
            billing_profiles (TenantBillingProfileRepositoryPort): Billing data.
            users (UserRepositoryPort): The tenant's client account.
            subscriptions (SubscriptionRepositoryPort): Its plan.
            plans (PlanRepositoryPort): Plan names.
            project_repo (ProjectRepositoryPort): Its projects.
            agent_repo (AgentRepositoryPort): Their agents.
            channel_connection_repo (ChannelConnectionRepositoryPort): Their channels.
            workspace (PrepareLangflowSessionUseCase): Opens the tenant's Langflow.
            langflow (LangflowAdminPort): Flows and variable names.
        """
        self._billing = billing_profiles
        self._users = users
        self._subscriptions = subscriptions
        self._plans = plans
        self._projects = project_repo
        self._agents = agent_repo
        self._channels = channel_connection_repo
        self._workspace = workspace
        self._langflow = langflow

    async def execute(self, tenant_id: UUID) -> OnboardingStatus:
        """Compute the status.

        Args:
            tenant_id (UUID): The tenant (scope already checked by the caller).

        Returns:
            OnboardingStatus: Checklist and next wizard step. Langflow being
            down only turns the Langflow-dependent checks into "unknown".
        """
        checks: List[OnboardingCheck] = []

        profile = await self._billing.get_by_tenant_id(tenant_id)
        billing_ok = bool(profile and profile.billing_email)
        checks.append(OnboardingCheck("billing", "ok" if billing_ok else "missing", profile.legal_name if profile else None))

        clients = [u for u in await self._users.list() if u.role == "client" and tenant_id in u.tenant_ids]
        if not clients:
            checks.append(OnboardingCheck("client_account", "missing"))
        else:
            status = clients[0].status
            checks.append(OnboardingCheck("client_account", "ok" if status == "active" else "warning", status))

        subscription = await self._subscriptions.get(tenant_id)
        plan = await self._plans.get(subscription.plan_id) if subscription else None
        checks.append(OnboardingCheck("plan", "ok" if plan else "missing", plan.name if plan else None))

        projects = sorted(await self._projects.list_by_tenant(tenant_id), key=lambda p: p.name.lower())
        project = projects[0] if projects else None
        checks.append(OnboardingCheck("project", "ok" if project else "missing", project.name if project else None))

        agents = [a for p in projects for a in await self._agents.list_by_project(p.id)]
        default = next((a for a in agents if a.is_default), agents[0] if agents else None)
        checks.extend(await self._langflow_checks(tenant_id, default))

        channels = [c for p in projects for c in await self._channels.list_by_project(p.id)]
        checks.append(OnboardingCheck("channel", "ok" if channels else "warning", str(len(channels))))

        if not billing_ok:
            step: WizardStep = "company"
        elif plan is None:
            step = "plan"
        elif project is None:
            step = "project"
        elif default is None:
            step = "agent"
        else:
            step = "summary"
        return OnboardingStatus(
            tenant_id=tenant_id, next_step=step, project_id=project.id if project else None, checks=checks
        )

    async def _langflow_checks(self, tenant_id: UUID, agent: Optional[Agent]) -> List[OnboardingCheck]:
        """The checks that need the tenant's Langflow: the default agent's
        flow still exists, and its LLM has an API key (the base agent is
        created without one; it is set by hand per client).

        Args:
            tenant_id (UUID): The tenant.
            agent (Optional[Agent]): Its default agent, if any.

        Returns:
            List[OnboardingCheck]: The "agent" and "openai_key" checks.
        """
        if agent is None:
            return [OnboardingCheck("agent", "missing"), OnboardingCheck("openai_key", "missing")]
        try:
            workspace = await self._workspace.open_workspace(tenant_id)
            folder = workspace.folders.get(agent.project_id)
            flows = await self._langflow.list_flows(workspace.tokens.access_token, folder) if folder else []
            if not any(f.id == agent.langflow_flow_id for f in flows):
                return [OnboardingCheck("agent", "warning", agent.name), OnboardingCheck("openai_key", "unknown")]
            configured = await self._langflow.llm_key_configured(workspace.tokens.access_token, agent.langflow_flow_id)
            key_status: CheckStatus = "missing" if configured is False else "ok"
            return [OnboardingCheck("agent", "ok", agent.name), OnboardingCheck("openai_key", key_status)]
        except (LangflowSessionError, LangflowTargetNotFoundError):
            logger.warning("onboarding.langflow_unavailable", extra={"tenant_id": str(tenant_id)})
            return [OnboardingCheck("agent", "unknown", agent.name), OnboardingCheck("openai_key", "unknown")]
