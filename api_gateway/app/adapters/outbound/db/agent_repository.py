"""SQLAlchemy implementation of AgentRepositoryPort."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.agent import Agent
from ....domain.ports.outbound import AgentRepositoryPort
from .models import AgentModel


def _to_domain(model: AgentModel) -> Agent:
    """Convert an AgentModel row into an Agent domain object.

    Args:
        model (AgentModel): The ORM row to convert.

    Returns:
        Agent: The equivalent domain object.
    """
    return Agent(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        langflow_flow_id=model.langflow_flow_id,
        config=model.config,
        is_default=model.is_default,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyAgentRepository(AgentRepositoryPort):
    """Postgres-backed implementation of AgentRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        langflow_flow_id: str,
        config: dict,
        is_default: bool,
    ) -> Agent:
        """Insert a new agent row.

        Args:
            project_id (UUID): Id of the owning project.
            name (str): Display name of the agent.
            langflow_flow_id (str): Id of the Langflow flow this agent runs.
            config (dict): Arbitrary agent configuration.
            is_default (bool): Whether this is the project's default agent.

        Returns:
            Agent: The created agent.
        """
        async with self._sessionmaker() as session:
            model = AgentModel(
                project_id=project_id,
                name=name,
                langflow_flow_id=langflow_flow_id,
                config=config or {},
                is_default=is_default,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Fetch an agent by id.

        Args:
            agent_id (UUID): Id of the agent.

        Returns:
            Optional[Agent]: The agent, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(AgentModel, agent_id)
            return _to_domain(model) if model else None

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[Agent]:
        """List agents, optionally filtered by project.

        Args:
            project_id (Optional[UUID]): If given, only return agents
                owned by this project.

        Returns:
            List[Agent]: The matching agents, ordered by creation date.
        """
        async with self._sessionmaker() as session:
            stmt = select(AgentModel).order_by(AgentModel.created_at)
            if project_id is not None:
                stmt = stmt.where(AgentModel.project_id == project_id)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, agent_id: UUID, **fields: Any) -> Optional[Agent]:
        """Update an agent's fields.

        Args:
            agent_id (UUID): Id of the agent to update.
            **fields (Any): Fields to update; None values are ignored.

        Returns:
            Optional[Agent]: The updated agent, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(AgentModel, agent_id)
            if not model:
                return None
            for key, value in fields.items():
                if value is not None:
                    setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def delete(self, agent_id: UUID) -> bool:
        """Delete an agent.

        Args:
            agent_id (UUID): Id of the agent to delete.

        Returns:
            bool: True if an agent was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(AgentModel, agent_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
