"""An in-memory "world" for exercising the admin API's authorization end to end.

Two tenants (A and B), each with a project, an agent, a workflow and a channel
connection, plus one console user per role attached to tenant A. Requests go
through the real routers, dependencies, `AccessControl` and use cases; only the
persistence and Redis are fakes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.adapters.inbound.http.admin import router as admin_router
from app.application.services.access_control import AccessControl
from app.application.use_cases.create_tenant import CreateTenantUseCase
from app.application.use_cases.create_user import CreateUserUseCase
from app.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.manage_profile import RemoveAvatarUseCase, SetAvatarUseCase
from app.application.use_cases.manage_users import DeleteUserUseCase, UpdateUserUseCase
from app.application.use_cases.provision_user import ProvisionUserUseCase
from app.core.config import settings
from app.domain.models.agent import Agent
from app.domain.models.project import Project
from app.domain.models.workflow_config import WorkflowConfig
from app.domain.ports.outbound import AlreadyExistsError
from api_gateway.tests.support.asgi import client_for_router
from app.application.services.quota_gate import QuotaGate
from app.application.use_cases.billing import (
    CloseBillingPeriodUseCase,
    ComputeStatementUseCase,
    ListUnratedMetersUseCase,
    PlanPricingInsightUseCase,
)
from app.application.use_cases.conversation_queries import GetConversationDetailUseCase
from app.application.use_cases.manage_agents import ManageAgentsUseCase, ProjectFlow
from api_gateway.tests.support.fakes import (
    FakeAccountTokenStore,
    FakeConversationRepository,
    FakeCostRateRepo,
    FakePlanRepo,
    FakeQuotaCounter,
    FakeStatementRepo,
    FakeSubscriptionRepo,
    FakeUsageStore,
    make_conversation,
    FakeAuthSessionRepo,
    FakeEmailSender,
    FakePasswordHasher,
    FakeTenantBillingProfileRepo,
    FakeUserAvatarRepo,
    FakeUserRepo,
    make_channel_connection,
    make_tenant,
    make_user,
)

CSRF = {"X-Requested-With": "fd-console"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryRepo:
    """Generic id-keyed store behind the admin repository ports.

    `build` turns the kwargs of `create` into a domain object; `owner_field`
    is the attribute `list_by_*` filters on (`project_id` / `tenant_id`).
    """

    def __init__(self, build, owner_field: Optional[str] = None, unique_key=None) -> None:
        self.items: Dict[UUID, Any] = {}
        self._build = build
        self._owner = owner_field
        # Como la restricción UNIQUE de la base: create() repetido -> AlreadyExistsError.
        self._unique_key = unique_key

    def add(self, item: Any) -> Any:
        self.items[item.id] = item
        return item

    async def create(self, **fields: Any) -> Any:
        item = self._build(**fields)
        if self._unique_key and any(self._unique_key(i) == self._unique_key(item) for i in self.items.values()):
            raise AlreadyExistsError("duplicate")
        return self.add(item)

    async def get_by_id(self, item_id: UUID) -> Optional[Any]:
        return self.items.get(item_id)

    async def _filtered(self, owner_id: Optional[UUID]) -> List[Any]:
        return [i for i in self.items.values() if owner_id is None or getattr(i, self._owner) == owner_id]

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[Any]:
        return await self._filtered(project_id)

    async def list_by_tenant(self, tenant_id: Optional[UUID] = None) -> List[Any]:
        return await self._filtered(tenant_id)

    async def list(self) -> List[Any]:
        return list(self.items.values())

    async def list_by_ids(self, ids: List[UUID]) -> List[Any]:
        return [i for i in self.items.values() if i.id in ids]

    async def update(self, item_id: UUID, **fields: Any) -> Optional[Any]:
        item = self.items.get(item_id)
        if item is None:
            return None
        self.items[item_id] = item.model_copy(update={k: v for k, v in fields.items() if v is not None})
        return self.items[item_id]

    async def delete(self, item_id: UUID) -> bool:
        return self.items.pop(item_id, None) is not None


class ConnectionUseCases:
    """Minimal stand-ins for the channel-connection use cases (they only need
    to persist through the repo; webhook registration is not under test here)."""

    def __init__(self, repo: InMemoryRepo) -> None:
        self._repo = repo

    async def create(self, **fields: Any):
        return await self._repo.create(**fields)

    async def update(self, connection_id: UUID, **fields: Any):
        return await self._repo.update(connection_id, **fields)

    async def delete(self, connection_id: UUID):
        return await self._repo.delete(connection_id)


class World:
    """Seeded data + helpers. Build with `World.build()`."""

    def __init__(self) -> None:
        now = _now()
        self.tenant_a = make_tenant(name="Tenant A", slug="a")
        self.tenant_b = make_tenant(name="Tenant B", slug="b")
        self.tenants = InMemoryRepo(lambda **f: make_tenant(**f), unique_key=lambda t: t.slug)
        self.projects = InMemoryRepo(
            lambda **f: Project(id=uuid4(), status="active", created_at=now, updated_at=now, **f),
            "tenant_id",
            unique_key=lambda p: (p.tenant_id, p.slug),
        )
        self.agents = InMemoryRepo(
            lambda **f: Agent(id=uuid4(), status="active", created_at=now, updated_at=now, **f), "project_id"
        )
        self.workflows = InMemoryRepo(
            lambda **f: WorkflowConfig(id=uuid4(), status="active", created_at=now, updated_at=now, **f),
            "project_id",
        )
        self.connections = InMemoryRepo(
            lambda **f: make_channel_connection(**f), "project_id", unique_key=lambda c: (c.channel_type, c.external_id)
        )
        for t in (self.tenant_a, self.tenant_b):
            self.tenants.add(t)

        self.project_a = self.projects.add(Project(id=uuid4(), tenant_id=self.tenant_a.id, name="PA", slug="pa", created_at=now, updated_at=now))
        self.project_b = self.projects.add(Project(id=uuid4(), tenant_id=self.tenant_b.id, name="PB", slug="pb", created_at=now, updated_at=now))
        self.agent_a = self.agents.add(Agent(id=uuid4(), project_id=self.project_a.id, name="AA", langflow_flow_id="fa", created_at=now, updated_at=now))
        self.agent_b = self.agents.add(Agent(id=uuid4(), project_id=self.project_b.id, name="AB", langflow_flow_id="fb", created_at=now, updated_at=now))
        self.workflow_a = self.workflows.add(WorkflowConfig(id=uuid4(), project_id=self.project_a.id, name="WA", n8n_workflow_id="na", created_at=now, updated_at=now))
        self.workflow_b = self.workflows.add(WorkflowConfig(id=uuid4(), project_id=self.project_b.id, name="WB", n8n_workflow_id="nb", created_at=now, updated_at=now))
        self.conn_a = self.connections.add(make_channel_connection(project_id=self.project_a.id, agent_id=self.agent_a.id, external_id="ca"))
        self.conn_b = self.connections.add(make_channel_connection(project_id=self.project_b.id, agent_id=self.agent_b.id, external_id="cb"))

        self.users = FakeUserRepo()
        self.sessions = FakeAuthSessionRepo()
        self.by_role: Dict[str, Any] = {}
        for role in ("admin", "tenant_manager", "botmaster", "client", "consultant"):
            tenant_ids = [] if role == "admin" else [self.tenant_a.id]
            self.by_role[role] = self.users.add(make_user(email=f"{role}@x.com", role=role, tenant_ids=tenant_ids))
        self.hasher = FakePasswordHasher()
        self.activation_tokens = FakeAccountTokenStore()
        self.mailer = FakeEmailSender()
        self.billing_profiles = FakeTenantBillingProfileRepo()
        self.avatars = FakeUserAvatarRepo(self.users)

        # Conversations and billing (one conversation per tenant).
        self.conversation_a = make_conversation(tenant_id=self.tenant_a.id, project_id=self.project_a.id, contact="+34 600 111")
        self.conversation_b = make_conversation(tenant_id=self.tenant_b.id, project_id=self.project_b.id, contact="+34 600 222")
        self.conversations = FakeConversationRepository(self.conversation_a, self.conversation_b)
        self.archived_messages: List[Any] = []
        self.usage = FakeUsageStore()
        self.cost_rates = FakeCostRateRepo()
        self.plans = FakePlanRepo()
        self.subscriptions = FakeSubscriptionRepo()
        self.plans.subscriptions = self.subscriptions
        self.statements = FakeStatementRepo()
        self.quota_gate = QuotaGate(subscriptions=self.subscriptions, plans=self.plans, counters=FakeQuotaCounter())
        # Flows in each project's Langflow folder (what the console may register as agents).
        self.langflow_flows: Dict[UUID, List[str]] = {
            self.project_a.id: ["f", "fa", "f2"],
            self.project_b.id: ["f", "fb"],
        }

    @classmethod
    def build(cls) -> "World":
        return cls()

    async def token(self, role_or_user) -> str:
        """Open a session for a role name or a User and return its cookie value."""
        user = self.by_role[role_or_user] if isinstance(role_or_user, str) else role_or_user
        return await self.sessions.create(user.id, ttl_seconds=3600)

    def state(self) -> Dict[str, Any]:
        conn_uc = ConnectionUseCases(self.connections)
        get_current = GetCurrentUserUseCase(
            sessions=self.sessions, user_repo=self.users, tenant_repo=self.tenants, session_ttl_seconds=3600
        )
        provision_user = self.provision_user_use_case()
        return dict(
            tenant_repo=self.tenants,
            tenant_billing_profile_repo=self.billing_profiles,
            project_repo=self.projects,
            agent_repo=self.agents,
            workflow_config_repo=self.workflows,
            channel_connection_repo=self.connections,
            user_repo=self.users,
            get_current_user_use_case=get_current,
            access_control=AccessControl(project_repo=self.projects, agent_repo=self.agents),
            create_channel_connection_use_case=type("C", (), {"execute": staticmethod(conn_uc.create)})(),
            update_channel_connection_use_case=type("U", (), {"execute": staticmethod(conn_uc.update)})(),
            delete_channel_connection_use_case=type("D", (), {"execute": staticmethod(conn_uc.delete)})(),
            channel_app_repo=type("R", (), {"list": staticmethod(_empty_list)})(),
            create_user_use_case=CreateUserUseCase(user_repo=self.users, tenant_repo=self.tenants, hasher=self.hasher),
            update_user_use_case=UpdateUserUseCase(user_repo=self.users, tenant_repo=self.tenants, hasher=self.hasher, sessions=self.sessions),
            delete_user_use_case=DeleteUserUseCase(user_repo=self.users, sessions=self.sessions),
            user_avatar_repo=self.avatars,
            set_avatar_use_case=SetAvatarUseCase(avatar_repo=self.avatars),
            remove_avatar_use_case=RemoveAvatarUseCase(avatar_repo=self.avatars),
            provision_user_use_case=provision_user,
            create_tenant_use_case=CreateTenantUseCase(
                tenant_repo=self.tenants, user_repo=self.users, provision_user=provision_user
            ),
            **self.billing_state(),
            **self.agents_state(),
        )

    def agents_state(self) -> Dict[str, Any]:
        """`app.state` entries for the agents and Langflow flows endpoints."""
        world = self

        class _Flows:
            async def execute(self, project_id):
                agents = {a.langflow_flow_id: a.id for a in await world.agents.list_by_project(project_id)}
                return [ProjectFlow(id=f, name=f.upper(), description=None, agent_id=agents.get(f))
                        for f in world.langflow_flows.get(project_id, [])]

            async def rename(self, project_id, flow_id, name):
                world.renamed_flows.append((project_id, flow_id, name))

        self.renamed_flows: List[tuple] = []
        flows = _Flows()
        manage = ManageAgentsUseCase(agent_repo=self.agents, channel_connection_repo=self.connections, flows=flows)

        class _BaseAgent:
            """Registers a fake flow and the agent, like CreateBaseAgentUseCase."""

            calls: List[Dict[str, Any]] = []

            async def execute(self, *, project_id, assistant_name, tone, instructions):
                self.calls.append(dict(project_id=project_id, assistant_name=assistant_name, tone=tone, instructions=instructions))
                flow_id = f"base-{len(self.calls)}"
                world.langflow_flows.setdefault(project_id, []).append(flow_id)
                return await manage.create(project_id=project_id, name=assistant_name, langflow_flow_id=flow_id,
                                           is_default=True, verify_flow=False)

        class _Onboarding:
            async def execute(self, tenant_id):
                from app.application.use_cases.onboarding import OnboardingCheck, OnboardingStatus

                return OnboardingStatus(tenant_id=tenant_id, next_step="plan", project_id=None,
                                        checks=[OnboardingCheck("billing", "ok", "Acme")])

        class _DeleteProject:
            """Deletes the project, like DeleteProjectUseCase after its Langflow folder."""

            async def execute(self, project_id):
                if world.langflow_delete_error:
                    raise world.langflow_delete_error
                deleted = await world.projects.delete(project_id)
                if deleted:
                    world.deleted_langflow_folders.append(project_id)
                return deleted

        self.deleted_langflow_folders: List[Any] = []
        self.langflow_delete_error: Optional[Exception] = None
        self.base_agent = _BaseAgent()
        return dict(
            delete_project_use_case=_DeleteProject(),
            create_base_agent_use_case=self.base_agent,
            get_onboarding_status_use_case=_Onboarding(),
            list_project_flows_use_case=flows,
            manage_agents_use_case=manage,
        )

    def billing_state(self) -> Dict[str, Any]:
        """`app.state` entries for the conversations and billing routers."""
        world = self

        class _Archive:
            async def list_messages(self, *, tenant_id, conversation_id, limit=500):
                return [m for m in world.archived_messages if m.conversation_id == conversation_id and m.tenant_id == tenant_id]

        compute = ComputeStatementUseCase(
            usage_store=self.usage, cost_rates=self.cost_rates, plans=self.plans,
            subscriptions=self.subscriptions, statements=self.statements,
        )
        return dict(
            conversation_repo=self.conversations,
            cost_rate_repo=self.cost_rates,
            plan_repo=self.plans,
            subscription_repo=self.subscriptions,
            statement_repo=self.statements,
            quota_gate=self.quota_gate,
            get_conversation_detail_use_case=GetConversationDetailUseCase(
                conversations=self.conversations, archive=_Archive(), usage_store=self.usage, cost_rates=self.cost_rates
            ),
            compute_statement_use_case=compute,
            close_billing_period_use_case=CloseBillingPeriodUseCase(
                compute=compute, subscriptions=self.subscriptions, statements=self.statements
            ),
            plan_pricing_insight_use_case=PlanPricingInsightUseCase(
                usage_store=self.usage, cost_rates=self.cost_rates, plans=self.plans, subscriptions=self.subscriptions
            ),
            list_unrated_meters_use_case=ListUnratedMetersUseCase(usage_store=self.usage, cost_rates=self.cost_rates),
        )

    def provision_user_use_case(self) -> ProvisionUserUseCase:
        """Fresh `ProvisionUserUseCase` sharing this world's users/tokens/mailer fakes."""
        return ProvisionUserUseCase(
            create_user=CreateUserUseCase(user_repo=self.users, tenant_repo=self.tenants, hasher=self.hasher),
            user_repo=self.users,
            tokens=self.activation_tokens,
            mailer=self.mailer,
            ttl_seconds=86400,
            activation_base_url="https://app.flowsdone.test",
        )

    def client(self):
        """Async context manager yielding an httpx client on `/internal/admin`."""
        return client_for_router(admin_router, **self.state())


async def _empty_list():
    return []


def cookie(token: str) -> Dict[str, str]:
    """Cookie header carrying a session token."""
    return {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}"}
