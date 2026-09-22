"""Use cases for the embedded-Langflow single sign-on.

Flow: the console asks for a session for a tenant (`PrepareLangflowSession`),
which makes sure the tenant's Langflow user and one folder per project exist
and returns a single-use ticket. The browser then presents that ticket to the
gateway (`RedeemLangflowTicket`), which logs in to Langflow *server-side* and
hands the resulting session cookies to the browser. The Langflow password
never reaches the browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from app.domain.ports.outbound import (
    AlreadyExistsError,
    LangflowAccountRepositoryPort,
    LangflowAdminPort,
    LangflowTokens,
    ProjectRepositoryPort,
    SecretGeneratorPort,
    SsoTicketStorePort,
    TenantRepositoryPort,
)

# Where the Langflow frontend lists a project's flows. Anything the ticket
# carries must start with this prefix (see `RedeemLangflowTicket`).
_LANDING_ROOT = "/all"


class LangflowTargetNotFoundError(Exception):
    """The tenant, or the project within it, does not exist (maps to 404)."""


@dataclass(frozen=True)
class LangflowLanding:
    """What the SSO endpoint needs to finish the handover.

    Attributes:
        tokens (LangflowTokens): Session tokens to set as cookies.
        path (str): Langflow path to redirect to (the tenant's project folder).
    """

    tokens: LangflowTokens
    path: str


def _username_for(tenant_slug: str) -> str:
    """Langflow login name for a tenant.

    Args:
        tenant_slug (str): The tenant's unique slug.

    Returns:
        str: `tenant-<slug>`.
    """
    return f"tenant-{tenant_slug}"


class PrepareLangflowSessionUseCase:
    """Provision a tenant's Langflow user/folders and issue an SSO ticket."""

    def __init__(
        self,
        *,
        tenant_repo: TenantRepositoryPort,
        project_repo: ProjectRepositoryPort,
        accounts: LangflowAccountRepositoryPort,
        langflow: LangflowAdminPort,
        secret_generator: SecretGeneratorPort,
        tickets: SsoTicketStorePort,
        ticket_ttl_seconds: int,
    ) -> None:
        """Build the use case.

        Args:
            tenant_repo (TenantRepositoryPort): Resolves the tenant.
            project_repo (ProjectRepositoryPort): Lists the tenant's projects.
            accounts (LangflowAccountRepositoryPort): Tenant -> Langflow user, project -> folder.
            langflow (LangflowAdminPort): Talks to Langflow.
            secret_generator (SecretGeneratorPort): Generates the account password.
            tickets (SsoTicketStorePort): Issues the single-use ticket.
            ticket_ttl_seconds (int): Ticket lifetime.
        """
        self._tenants = tenant_repo
        self._projects = project_repo
        self._accounts = accounts
        self._langflow = langflow
        self._secrets = secret_generator
        self._tickets = tickets
        self._ttl = ticket_ttl_seconds

    async def execute(self, tenant_id: UUID, project_id: Optional[UUID] = None) -> str:
        """Make sure the tenant can be opened in Langflow and issue a ticket.

        Args:
            tenant_id (UUID): Tenant whose agents should be shown.
            project_id (Optional[UUID]): Project whose folder to land on; the
                first project (by name) when omitted.

        Returns:
            str: A single-use ticket to present to the SSO endpoint.

        Raises:
            LangflowTargetNotFoundError: If the tenant does not exist, or the
                project is not one of its projects.
            LangflowSessionError: If Langflow fails.
        """
        tenant = await self._tenants.get_by_id(tenant_id)
        if tenant is None:
            raise LangflowTargetNotFoundError("tenant not found")
        projects = sorted(await self._projects.list_by_tenant(tenant_id), key=lambda p: p.name.lower())
        target = None
        if project_id is not None:
            target = next((p for p in projects if p.id == project_id), None)
            if target is None:
                raise LangflowTargetNotFoundError("project not found")
        elif projects:
            target = projects[0]

        account = await self._ensure_account(tenant_id, _username_for(tenant.slug))
        tokens = await self._langflow.login(account.username, account.password.get_secret_value())
        folders = await self._ensure_folders(tokens, projects)

        path = f"{_LANDING_ROOT}/folder/{folders[target.id]}" if target else _LANDING_ROOT
        return await self._tickets.issue({"tenant_id": str(tenant_id), "path": path}, ttl_seconds=self._ttl)

    async def _ensure_account(self, tenant_id: UUID, username: str):
        """Get the tenant's Langflow account, creating it (and the Langflow user) if needed.

        The row is stored *first*, so the password Langflow ends up with is
        always the stored one, even if two requests race or Langflow fails
        half-way: the next attempt repeats `ensure_user` with the same password.

        Args:
            tenant_id (UUID): The tenant.
            username (str): Langflow login name to use if the account is new.

        Returns:
            LangflowAccount: The account, with `langflow_user_id` set.
        """
        account = await self._accounts.get(tenant_id)
        if account is None:
            try:
                account = await self._accounts.create(
                    tenant_id=tenant_id, username=username, password=self._secrets.generate()
                )
            except AlreadyExistsError:
                account = await self._accounts.get(tenant_id)
        if account.langflow_user_id is None:
            user_id = await self._langflow.ensure_user(account.username, account.password.get_secret_value())
            await self._accounts.set_langflow_user_id(tenant_id, user_id)
            account = account.model_copy(update={"langflow_user_id": user_id})
        return account

    async def _ensure_folders(self, tokens: LangflowTokens, projects) -> dict:
        """Make sure every project has a folder in the tenant's Langflow.

        A stored folder id that Langflow no longer knows (someone deleted it
        there) is replaced by a new folder.

        Args:
            tokens (LangflowTokens): The tenant user's session.
            projects: The tenant's projects.

        Returns:
            dict: Project id -> Langflow folder id.
        """
        existing = await self._langflow.list_projects(tokens.access_token) if projects else {}
        result = {}
        for project in projects:
            folder_id = await self._accounts.get_folder(project.id)
            if folder_id is None or folder_id not in existing:
                folder_id = await self._langflow.create_project(tokens.access_token, project.name)
                await self._accounts.save_folder(project.id, folder_id)
            result[project.id] = folder_id
        return result


class RedeemLangflowTicketUseCase:
    """Exchange an SSO ticket for a logged-in Langflow session."""

    def __init__(
        self,
        *,
        accounts: LangflowAccountRepositoryPort,
        langflow: LangflowAdminPort,
        tickets: SsoTicketStorePort,
    ) -> None:
        """Build the use case.

        Args:
            accounts (LangflowAccountRepositoryPort): Tenant -> Langflow user.
            langflow (LangflowAdminPort): Talks to Langflow.
            tickets (SsoTicketStorePort): Consumes the ticket.
        """
        self._accounts = accounts
        self._langflow = langflow
        self._tickets = tickets

    async def execute(self, ticket: str) -> Optional[LangflowLanding]:
        """Redeem a ticket and log in to Langflow as the tenant's user.

        Args:
            ticket (str): The value the browser presented.

        Returns:
            Optional[LangflowLanding]: Tokens and landing path, or None when
            the ticket is unknown, already used or expired.

        Raises:
            LangflowSessionError: If Langflow refuses the login.
        """
        payload = await self._tickets.redeem(ticket)
        if payload is None:
            return None
        account = await self._accounts.get(UUID(payload["tenant_id"]))
        if account is None:
            return None
        tokens = await self._langflow.login(account.username, account.password.get_secret_value())
        path = payload.get("path", _LANDING_ROOT)
        if path != _LANDING_ROOT and not path.startswith(_LANDING_ROOT + "/"):
            path = _LANDING_ROOT
        return LangflowLanding(tokens=tokens, path=path)
