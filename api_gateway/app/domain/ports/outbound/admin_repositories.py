"""Ports for the admin/tenancy repositories (tenants, projects, agents,
workflows, channel connections, channel apps).
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol
from uuid import UUID

from ....domain.models.agent import Agent
from ....domain.models.channel_app import ChannelApp
from ....domain.models.channel_connection import ChannelConnection
from ....domain.models.channel_resolution import ChannelResolution
from ....domain.models.project import Project
from ....domain.models.tenant import Tenant
from ....domain.models.workflow_config import WorkflowConfig


class TenantRepositoryPort(Protocol):
    """CRUD contract for tenants."""

    async def create(self, *, name: str, slug: str) -> Tenant:
        """Create a tenant.

        Args:
            name (str): Display name of the tenant.
            slug (str): Unique URL-safe identifier for the tenant.

        Returns:
            Tenant: The created tenant.
        """
        ...

    async def get_by_id(self, tenant_id: UUID) -> Optional[Tenant]:
        """Fetch a tenant by id.

        Args:
            tenant_id (UUID): Id of the tenant.

        Returns:
            Optional[Tenant]: The tenant, or None if it does not exist.
        """
        ...

    async def list(self) -> List[Tenant]:
        """List all tenants.

        Returns:
            List[Tenant]: All existing tenants.
        """
        ...

    async def update(self, tenant_id: UUID, **fields: Any) -> Optional[Tenant]:
        """Update a tenant's fields.

        Args:
            tenant_id (UUID): Id of the tenant to update.
            **fields (Any): Fields to update.

        Returns:
            Optional[Tenant]: The updated tenant, or None if it does
            not exist.
        """
        ...

    async def delete(self, tenant_id: UUID) -> bool:
        """Delete a tenant.

        Args:
            tenant_id (UUID): Id of the tenant to delete.

        Returns:
            bool: True if a tenant was deleted, False if it did not exist.
        """
        ...


class ProjectRepositoryPort(Protocol):
    """CRUD contract for projects (scoped to a tenant)."""

    async def create(self, *, tenant_id: UUID, name: str, slug: str) -> Project:
        """Create a project.

        Args:
            tenant_id (UUID): Id of the owning tenant.
            name (str): Display name of the project.
            slug (str): Unique URL-safe identifier for the project.

        Returns:
            Project: The created project.
        """
        ...

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Fetch a project by id.

        Args:
            project_id (UUID): Id of the project.

        Returns:
            Optional[Project]: The project, or None if it does not exist.
        """
        ...

    async def list_by_tenant(self, tenant_id: Optional[UUID] = None) -> List[Project]:
        """List projects, optionally filtered by tenant.

        Args:
            tenant_id (Optional[UUID]): If given, only return projects
                owned by this tenant.

        Returns:
            List[Project]: The matching projects.
        """
        ...

    async def update(self, project_id: UUID, **fields: Any) -> Optional[Project]:
        """Update a project's fields.

        Args:
            project_id (UUID): Id of the project to update.
            **fields (Any): Fields to update.

        Returns:
            Optional[Project]: The updated project, or None if it does
            not exist.
        """
        ...

    async def delete(self, project_id: UUID) -> bool:
        """Delete a project.

        Args:
            project_id (UUID): Id of the project to delete.

        Returns:
            bool: True if a project was deleted, False if it did not exist.
        """
        ...


class AgentRepositoryPort(Protocol):
    """CRUD contract for Langflow agents (scoped to a project)."""

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        langflow_flow_id: str,
        config: dict,
        is_default: bool,
    ) -> Agent:
        """Create an agent.

        Args:
            project_id (UUID): Id of the owning project.
            name (str): Display name of the agent.
            langflow_flow_id (str): Id of the Langflow flow this agent runs.
            config (dict): Arbitrary agent configuration.
            is_default (bool): Whether this is the project's default agent.

        Returns:
            Agent: The created agent.
        """
        ...

    async def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Fetch an agent by id.

        Args:
            agent_id (UUID): Id of the agent.

        Returns:
            Optional[Agent]: The agent, or None if it does not exist.
        """
        ...

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[Agent]:
        """List agents, optionally filtered by project.

        Args:
            project_id (Optional[UUID]): If given, only return agents
                owned by this project.

        Returns:
            List[Agent]: The matching agents.
        """
        ...

    async def update(self, agent_id: UUID, **fields: Any) -> Optional[Agent]:
        """Update an agent's fields.

        Args:
            agent_id (UUID): Id of the agent to update.
            **fields (Any): Fields to update.

        Returns:
            Optional[Agent]: The updated agent, or None if it does not exist.
        """
        ...

    async def delete(self, agent_id: UUID) -> bool:
        """Delete an agent.

        Args:
            agent_id (UUID): Id of the agent to delete.

        Returns:
            bool: True if an agent was deleted, False if it did not exist.
        """
        ...


class WorkflowConfigRepositoryPort(Protocol):
    """CRUD contract for n8n workflow configurations (scoped to a project)."""

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        n8n_workflow_id: str,
        trigger_type: str,
        config: dict,
    ) -> WorkflowConfig:
        """Create a workflow configuration.

        Args:
            project_id (UUID): Id of the owning project.
            name (str): Display name of the workflow configuration.
            n8n_workflow_id (str): Id of the n8n workflow it triggers.
            trigger_type (str): How the workflow is triggered (e.g. "webhook").
            config (dict): Arbitrary trigger configuration.

        Returns:
            WorkflowConfig: The created workflow configuration.
        """
        ...

    async def get_by_id(self, workflow_id: UUID) -> Optional[WorkflowConfig]:
        """Fetch a workflow configuration by id.

        Args:
            workflow_id (UUID): Id of the workflow configuration.

        Returns:
            Optional[WorkflowConfig]: The workflow configuration, or
            None if it does not exist.
        """
        ...

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[WorkflowConfig]:
        """List workflow configurations, optionally filtered by project.

        Args:
            project_id (Optional[UUID]): If given, only return configs
                owned by this project.

        Returns:
            List[WorkflowConfig]: The matching workflow configurations.
        """
        ...

    async def update(self, workflow_id: UUID, **fields: Any) -> Optional[WorkflowConfig]:
        """Update a workflow configuration's fields.

        Args:
            workflow_id (UUID): Id of the workflow configuration to update.
            **fields (Any): Fields to update.

        Returns:
            Optional[WorkflowConfig]: The updated workflow configuration,
            or None if it does not exist.
        """
        ...

    async def delete(self, workflow_id: UUID) -> bool:
        """Delete a workflow configuration.

        Args:
            workflow_id (UUID): Id of the workflow configuration to delete.

        Returns:
            bool: True if a config was deleted, False if it did not exist.
        """
        ...


class ChannelConnectionRepositoryPort(Protocol):
    """CRUD contract for channel connections (a project's link to a
    specific WhatsApp/Facebook/Instagram/Telegram/X/TikTok account).
    """

    async def create(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        channel_type: str,
        external_id: str,
        display_name: Optional[str],
        credentials: dict,
        config: dict,
    ) -> ChannelConnection:
        """Create a channel connection.

        Args:
            project_id (UUID): Id of the owning project.
            agent_id (UUID): Id of the agent that answers messages on
                this channel.
            channel_type (str): Channel type (e.g. "whatsapp_evolution",
                "telegram").
            external_id (str): Identifier used to route inbound webhooks
                (instance name, page id, bot token, etc., depending on
                the channel).
            display_name (Optional[str]): Optional human-readable label.
            credentials (dict): Channel credentials, stored encrypted
                at rest.
            config (dict): Arbitrary channel configuration.

        Returns:
            ChannelConnection: The created channel connection.
        """
        ...

    async def get_by_id(self, channel_connection_id: UUID) -> Optional[ChannelConnection]:
        """Fetch a channel connection by id.

        Args:
            channel_connection_id (UUID): Id of the channel connection.

        Returns:
            Optional[ChannelConnection]: The channel connection, or
            None if it does not exist.
        """
        ...

    async def get_by_channel_and_external_id(
        self, channel_type: str, external_id: str
    ) -> Optional[ChannelResolution]:
        """Resolve an inbound webhook to its tenant/project/agent.

        Args:
            channel_type (str): Channel type of the incoming webhook.
            external_id (str): External id carried by the webhook
                (instance name, page id, bot token, etc.).

        Returns:
            Optional[ChannelResolution]: A resolution with
            tenant/project/agent context and decrypted credentials, or
            None if no active connection matches.
        """
        ...

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[ChannelConnection]:
        """List channel connections, optionally filtered by project.

        Args:
            project_id (Optional[UUID]): If given, only return
                connections owned by this project.

        Returns:
            List[ChannelConnection]: The matching channel connections.
        """
        ...

    async def update(self, channel_connection_id: UUID, **fields: Any) -> Optional[ChannelConnection]:
        """Update a channel connection's fields.

        Args:
            channel_connection_id (UUID): Id of the connection to update.
            **fields (Any): Fields to update.

        Returns:
            Optional[ChannelConnection]: The updated channel connection,
            or None if it does not exist.
        """
        ...

    async def delete(self, channel_connection_id: UUID) -> bool:
        """Delete a channel connection.

        Args:
            channel_connection_id (UUID): Id of the connection to delete.

        Returns:
            bool: True if a connection was deleted, False if it did
            not exist.
        """
        ...


class ChannelAppRepositoryPort(Protocol):
    """CRUD contract for shared provider app credentials.

    Meta (Facebook + Instagram), X, and TikTok are accessed through a
    single shared app per provider for the whole SaaS, not per tenant.
    `provider` is the natural key: only a handful of rows can ever
    exist, hence `upsert` instead of separate create/update-by-id
    methods.
    """

    async def upsert(self, *, provider: str, credentials: dict, config: dict) -> ChannelApp:
        """Create or replace the shared app credentials for a provider.

        Args:
            provider (str): Provider identifier (e.g. "meta", "twitter",
                "tiktok").
            credentials (dict): App credentials, stored encrypted at rest.
            config (dict): Arbitrary app configuration.

        Returns:
            ChannelApp: The upserted channel app.
        """
        ...

    async def get_by_provider(self, provider: str) -> Optional[ChannelApp]:
        """Fetch the active app credentials for a provider.

        Args:
            provider (str): Provider identifier.

        Returns:
            Optional[ChannelApp]: The channel app, or None if it does
            not exist or is inactive.
        """
        ...

    async def list(self) -> List[ChannelApp]:
        """List all provider app credential records.

        Returns:
            List[ChannelApp]: All existing channel app records.
        """
        ...

    async def delete(self, provider: str) -> bool:
        """Delete a provider's app credentials.

        Args:
            provider (str): Provider identifier.

        Returns:
            bool: True if a record was deleted, False if it did not exist.
        """
        ...
