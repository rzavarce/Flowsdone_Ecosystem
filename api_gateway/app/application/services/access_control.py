"""Authorization for the admin API: who may do what, on which tenants.

Two independent questions are answered here, both HTTP-agnostic:

1. **Role**: may this role perform `action` on `resource`? (`POLICY`)
2. **Scope**: is the target inside a tenant the caller can see?
   Everything below a tenant (projects, agents, workflows, channel
   connections) hangs off a project, so scope is always resolved through
   `project.tenant_id`.

Out-of-scope resources are reported as *not found* (never "forbidden"), so
a caller cannot probe which ids exist in other tenants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, FrozenSet, List, Literal, Optional
from uuid import UUID

from app.application.dto.auth_dto import AuthenticatedUser
from app.domain.models.project import Project
from app.domain.ports.outbound import AgentRepositoryPort, ProjectRepositoryPort

__all__ = [
    "AccessControl",
    "AccessDeniedError",
    "InvalidReferenceError",
    "POLICY",
    "Principal",
    "ResourceNotFoundError",
]

Resource = Literal[
    "tenants",
    "projects",
    "agents",
    "workflows",
    "channel_connections",
    "channel_apps",
    "users",
    "langflow",
    "tenant_billing",
    "conversations",
    "plans",
    "cost_rates",
    "billing",
]
Action = Literal["read", "write"]

_ALL_STAFF = frozenset({"admin", "tenant_manager", "botmaster"})
_MANAGERS = frozenset({"admin", "tenant_manager"})
_ADMIN = frozenset({"admin"})

# role x resource x action. The single source of truth for the admin API:
#  - tenant_manager: everything inside their tenants, but cannot create or
#    delete tenants, touch the global provider credentials (channel_apps),
#    or manage users.
#  - botmaster: Flowsdone staff assigned to specific tenants (by an admin,
#    via user_tenants); builds/edits agents and manages those tenants'
#    channel connections. Everything else is read-only or hidden.
#  - client: no access to the admin API at all (dashboards only).
POLICY: dict[str, dict[str, FrozenSet[str]]] = {
    "tenants": {"read": _ALL_STAFF, "write": _ADMIN},
    "projects": {"read": _ALL_STAFF, "write": _MANAGERS},
    "agents": {"read": _ALL_STAFF, "write": _ALL_STAFF},
    "workflows": {"read": _ALL_STAFF, "write": _MANAGERS},
    "channel_connections": {"read": _ALL_STAFF, "write": _ALL_STAFF},
    "channel_apps": {"read": _ADMIN, "write": _ADMIN},
    "users": {"read": _ADMIN, "write": _ADMIN},
    # Opening the Langflow editor as a tenant's user. Any staff role, scoped
    # to their own tenants by access.tenant() as usual - but the per-tenant
    # separation *inside* Langflow is a view, not a security boundary: an
    # editor can add a Python-code component that runs in the shared
    # `langflow` container and reaches its env vars (GATEWAY_ADMIN_API_KEY,
    # Langfuse/Weaviate credentials) and the internal network. Accepted
    # knowingly for tenant_manager/botmaster (Flowsdone staff, not clients).
    "langflow": {"read": _ALL_STAFF, "write": _ALL_STAFF},
    # Billing/company data of a tenant (domain/models/tenant_billing_profile.py).
    # A client sees their own read-only through /me/billing-profile instead
    # of this - never through the admin API (see users, above).
    "tenant_billing": {"read": _MANAGERS, "write": _MANAGERS},
    # Conversation inbox (records, transcripts, per-conversation cost) of
    # the caller's tenants. Nothing writes through it yet.
    "conversations": {"read": _ALL_STAFF, "write": _MANAGERS},
    # Commercial plans and the cost catalog: Flowsdone's own pricing and
    # costs, admin only.
    "plans": {"read": _ADMIN, "write": _ADMIN},
    "cost_rates": {"read": _ADMIN, "write": _ADMIN},
    # A tenant's subscription, usage and statements. Managers read them
    # for their tenants (costs/margin are stripped for anyone but admin,
    # see admin/billing.py); only admin assigns plans or closes periods.
    "billing": {"read": _MANAGERS, "write": _ADMIN},
}


class AccessDeniedError(Exception):
    """The caller's role may not perform this action (maps to 403)."""


class ResourceNotFoundError(Exception):
    """The target does not exist *or lies outside the caller's tenants* (404)."""

    def __init__(self, resource: str) -> None:
        """Build the error.

        Args:
            resource (str): Human name used in the message (e.g. "agent").
        """
        super().__init__(f"{resource} not found")
        self.resource = resource


class InvalidReferenceError(Exception):
    """A body references something that does not belong together (maps to 400)."""


@dataclass(frozen=True)
class Principal:
    """The authenticated caller, whether a person or a machine.

    Attributes:
        role (str): One of the `UserRole` values. Machine callers (admin API
            key) are `admin`.
        tenant_ids (Optional[FrozenSet[UUID]]): Tenants the caller may see;
            `None` means all of them.
        user_id (Optional[UUID]): The user, or None for the API key.
    """

    role: str
    tenant_ids: Optional[FrozenSet[UUID]]
    user_id: Optional[UUID] = None

    @classmethod
    def machine(cls) -> "Principal":
        """Principal for the shared `X-Admin-Api-Key` (scripts, CI, Postman)."""
        return cls(role="admin", tenant_ids=None)

    @classmethod
    def from_user(cls, user: AuthenticatedUser) -> "Principal":
        """Principal for a signed-in console user.

        Args:
            user (AuthenticatedUser): The session's user.

        Returns:
            Principal: Admins see every tenant; everyone else only theirs.
        """
        tenants = None if user.role == "admin" else frozenset(t.id for t in user.tenants)
        return cls(role=user.role, tenant_ids=tenants, user_id=user.id)

    @property
    def unrestricted(self) -> bool:
        """True when the caller can see every tenant."""
        return self.tenant_ids is None

    def can_see_tenant(self, tenant_id: UUID) -> bool:
        """Whether a tenant is inside the caller's scope.

        Args:
            tenant_id (UUID): Tenant to check.

        Returns:
            bool: True for unrestricted callers or member tenants.
        """
        return self.tenant_ids is None or tenant_id in self.tenant_ids


class AccessControl:
    """Applies `POLICY` and tenant scoping. Stateless apart from its repos."""

    def __init__(self, *, project_repo: ProjectRepositoryPort, agent_repo: AgentRepositoryPort) -> None:
        """Build the service.

        Args:
            project_repo (ProjectRepositoryPort): Resolves a project's tenant.
            agent_repo (AgentRepositoryPort): Validates agent/project pairs.
        """
        self._projects = project_repo
        self._agents = agent_repo

    @staticmethod
    def authorize(principal: Principal, resource: str, action: str) -> None:
        """Check the role-level permission.

        Args:
            principal (Principal): The caller.
            resource (str): A key of `POLICY`.
            action (str): `read` or `write`.

        Raises:
            AccessDeniedError: If the role is not allowed (including `client`,
                which appears nowhere in `POLICY`).
        """
        if principal.role not in POLICY[resource][action]:
            raise AccessDeniedError(f"{principal.role} cannot {action} {resource}")

    @staticmethod
    def ensure_tenant(principal: Principal, tenant_id: UUID, *, resource: str = "tenant") -> None:
        """Require a tenant to be inside the caller's scope.

        Args:
            principal (Principal): The caller.
            tenant_id (UUID): Tenant to check.
            resource (str): Name used in the not-found error.

        Raises:
            ResourceNotFoundError: If it is outside the caller's tenants.
        """
        if not principal.can_see_tenant(tenant_id):
            raise ResourceNotFoundError(resource)

    async def ensure_project(
        self, principal: Principal, project_id: UUID, *, resource: str = "project"
    ) -> Project:
        """Require a project to exist and belong to a visible tenant.

        Args:
            principal (Principal): The caller.
            project_id (UUID): Project to check.
            resource (str): Name used in the not-found error, so the message
                names what the caller asked for (e.g. "agent").

        Returns:
            Project: The project.

        Raises:
            ResourceNotFoundError: If it does not exist or is out of scope
                (indistinguishable on purpose).
        """
        project = await self._projects.get_by_id(project_id)
        if project is None or not principal.can_see_tenant(project.tenant_id):
            raise ResourceNotFoundError(resource)
        return project

    async def visible_projects(self, principal: Principal) -> List[Project]:
        """Projects of every tenant the caller can see.

        Args:
            principal (Principal): The caller.

        Returns:
            List[Project]: All projects for unrestricted callers; otherwise
            the projects of their tenants.
        """
        if principal.tenant_ids is None:
            return await self._projects.list_by_tenant(None)
        projects: List[Project] = []
        for tenant_id in principal.tenant_ids:
            projects.extend(await self._projects.list_by_tenant(tenant_id))
        return projects

    async def list_scoped(
        self,
        principal: Principal,
        list_by_project: Callable[[Optional[UUID]], Awaitable[List[Any]]],
        project_id: Optional[UUID],
        *,
        resource: str,
    ) -> List[Any]:
        """List project-owned items the caller is allowed to see.

        Args:
            principal (Principal): The caller.
            list_by_project (Callable): A repo's `list_by_project`.
            project_id (Optional[UUID]): Optional filter from the query string.
            resource (str): Name used in the not-found error.

        Returns:
            List[Any]: With a filter: that project's items (404 if the project
            is out of scope). Without one: unrestricted callers get
            everything, others the union over their tenants' projects.

        Raises:
            ResourceNotFoundError: If `project_id` is out of scope.
        """
        if project_id is not None:
            await self.ensure_project(principal, project_id, resource=resource)
            return await list_by_project(project_id)
        if principal.unrestricted:
            return await list_by_project(None)
        items: List[Any] = []
        for project in await self.visible_projects(principal):
            items.extend(await list_by_project(project.id))
        return items

    async def ensure_agent_in_project(self, agent_id: UUID, project_id: UUID) -> None:
        """Require an agent to belong to the given project.

        Prevents binding a channel to another tenant's agent (which would
        route this tenant's messages to it).

        Args:
            agent_id (UUID): Agent referenced by the request.
            project_id (UUID): Project the channel belongs to.

        Raises:
            InvalidReferenceError: If the agent does not exist or belongs to
                a different project.
        """
        agent = await self._agents.get_by_id(agent_id)
        if agent is None or agent.project_id != project_id:
            raise InvalidReferenceError("agent does not belong to the project")
