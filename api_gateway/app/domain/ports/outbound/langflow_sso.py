"""Ports for the embedded-Langflow single sign-on (tenant -> Langflow user)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol
from uuid import UUID

from app.domain.models.langflow_account import LangflowAccount


class LangflowSessionError(Exception):
    """Langflow refused or failed a request the SSO depends on (maps to 502)."""


@dataclass(frozen=True)
class LangflowTokens:
    """Tokens Langflow issues on login.

    Attributes:
        access_token (str): Short-lived JWT the Langflow frontend reads.
        refresh_token (str): Longer-lived token used to renew the access token.
    """

    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class LangflowFlowSummary:
    """A flow as listed in a Langflow folder.

    Attributes:
        id (str): Flow id (what an agent's `langflow_flow_id` points to).
        name (str): Flow name.
        description (Optional[str]): Flow description.
        updated_at (Optional[str]): Last change, ISO-8601 as Langflow sends it.
    """

    id: str
    name: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


class LangflowAccountRepositoryPort(Protocol):
    """Persistence of tenant -> Langflow user and project -> Langflow folder."""

    async def get(self, tenant_id: UUID) -> Optional[LangflowAccount]:
        """Fetch a tenant's Langflow account.

        Args:
            tenant_id (UUID): The tenant.

        Returns:
            Optional[LangflowAccount]: The account, or None if not created yet.
        """
        ...

    async def create(self, *, tenant_id: UUID, username: str, password: str) -> LangflowAccount:
        """Store a new account (password encrypted at rest).

        Args:
            tenant_id (UUID): The tenant.
            username (str): Langflow login name.
            password (str): Plain password to store encrypted.

        Returns:
            LangflowAccount: The stored account.

        Raises:
            AlreadyExistsError: If the tenant already has one (a concurrent request won).
        """
        ...

    async def set_langflow_user_id(self, tenant_id: UUID, langflow_user_id: str) -> None:
        """Record the id Langflow gave the user.

        Args:
            tenant_id (UUID): The tenant.
            langflow_user_id (str): Id of the user inside Langflow.
        """
        ...

    async def get_folder(self, project_id: UUID) -> Optional[str]:
        """Id of the Langflow project (folder) that mirrors a gateway project.

        Args:
            project_id (UUID): The gateway project.

        Returns:
            Optional[str]: The Langflow folder id, or None.
        """
        ...

    async def save_folder(self, project_id: UUID, folder_id: str) -> None:
        """Record (or replace) the Langflow folder of a gateway project.

        Args:
            project_id (UUID): The gateway project.
            folder_id (str): The Langflow folder id.
        """
        ...


class LangflowAdminPort(Protocol):
    """What the gateway needs from Langflow to provision and open sessions."""

    async def ensure_user(self, username: str, password: str) -> str:
        """Create the user (active) or, if it exists, reset its password.

        Idempotent: the stored password is the source of truth.

        Args:
            username (str): Langflow login name.
            password (str): Password the user must end up with.

        Returns:
            str: The user's id inside Langflow.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...

    async def login(self, username: str, password: str) -> LangflowTokens:
        """Log a user in.

        Args:
            username (str): Langflow login name.
            password (str): The user's password.

        Returns:
            LangflowTokens: The tokens Langflow issued.

        Raises:
            LangflowSessionError: If the login is refused or Langflow is unreachable.
        """
        ...

    async def list_projects(self, access_token: str) -> Dict[str, str]:
        """Projects (folders) of the logged-in user.

        Args:
            access_token (str): The user's access token.

        Returns:
            Dict[str, str]: Folder id -> name.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...

    async def create_project(self, access_token: str, name: str) -> str:
        """Create a project (folder) for the logged-in user.

        Args:
            access_token (str): The user's access token.
            name (str): Folder name.

        Returns:
            str: The new folder id.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...


    async def list_flows(self, access_token: str, folder_id: str) -> List[LangflowFlowSummary]:
        """Flows (not components) in one of the logged-in user's folders.

        Args:
            access_token (str): The user's access token.
            folder_id (str): The folder.

        Returns:
            List[LangflowFlowSummary]: The flows, by name.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...


    async def create_base_flow(self, access_token: str, folder_id: str, *, name: str, system_prompt: str) -> str:
        """Create the platform's base chat agent flow in one of the
        logged-in user's folders (chat input, conversation memory, the
        prompt, an LLM reading the `OPENAI_API_KEY` global variable, and
        chat output).

        Args:
            access_token (str): The user's access token.
            folder_id (str): Folder to create it in.
            name (str): Flow name.
            system_prompt (str): The agent's instructions (no template variables).

        Returns:
            str: The new flow's id.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...

    async def list_variable_names(self, access_token: str) -> List[str]:
        """Names of the logged-in user's global variables (never their values).

        Args:
            access_token (str): The user's access token.

        Returns:
            List[str]: The names.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        ...


class SsoTicketStorePort(Protocol):
    """Single-use, short-lived tickets that hand a browser over to Langflow."""

    async def issue(self, payload: Dict[str, str], *, ttl_seconds: int) -> str:
        """Create a ticket.

        Args:
            payload (Dict[str, str]): Data to recover when it is redeemed.
            ttl_seconds (int): Lifetime.

        Returns:
            str: An unguessable opaque ticket.
        """
        ...

    async def redeem(self, ticket: str) -> Optional[Dict[str, str]]:
        """Consume a ticket (it works once).

        Args:
            ticket (str): The value presented by the browser.

        Returns:
            Optional[Dict[str, str]]: The payload, or None if unknown, used or expired.
        """
        ...
