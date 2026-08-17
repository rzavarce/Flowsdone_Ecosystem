"""SQLAlchemy implementation of WorkflowConfigRepositoryPort."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api_gateway.app.domain.models.workflow_config import WorkflowConfig
from api_gateway.app.domain.ports.outbound import WorkflowConfigRepositoryPort
from api_gateway.app.adapters.outbound.db.models import WorkflowConfigModel


def _to_domain(model: WorkflowConfigModel) -> WorkflowConfig:
    """Convert a WorkflowConfigModel row into a WorkflowConfig domain object.

    Args:
        model (WorkflowConfigModel): The ORM row to convert.

    Returns:
        WorkflowConfig: The equivalent domain object.
    """
    return WorkflowConfig(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        n8n_workflow_id=model.n8n_workflow_id,
        trigger_type=model.trigger_type,
        config=model.config,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyWorkflowConfigRepository(WorkflowConfigRepositoryPort):
    """Postgres-backed implementation of WorkflowConfigRepositoryPort."""

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
        n8n_workflow_id: str,
        trigger_type: str,
        config: dict,
    ) -> WorkflowConfig:
        """Insert a new workflow configuration row.

        Args:
            project_id (UUID): Id of the owning project.
            name (str): Display name of the workflow configuration.
            n8n_workflow_id (str): Id of the n8n workflow it triggers.
            trigger_type (str): How the workflow is triggered; defaults
                to "webhook" if falsy.
            config (dict): Arbitrary trigger configuration.

        Returns:
            WorkflowConfig: The created workflow configuration.
        """
        async with self._sessionmaker() as session:
            model = WorkflowConfigModel(
                project_id=project_id,
                name=name,
                n8n_workflow_id=n8n_workflow_id,
                trigger_type=trigger_type or "webhook",
                config=config or {},
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, workflow_id: UUID) -> Optional[WorkflowConfig]:
        """Fetch a workflow configuration by id.

        Args:
            workflow_id (UUID): Id of the workflow configuration.

        Returns:
            Optional[WorkflowConfig]: The workflow configuration, or
            None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(WorkflowConfigModel, workflow_id)
            return _to_domain(model) if model else None

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[WorkflowConfig]:
        """List workflow configurations, optionally filtered by project.

        Args:
            project_id (Optional[UUID]): If given, only return configs
                owned by this project.

        Returns:
            List[WorkflowConfig]: The matching workflow configurations,
            ordered by creation date.
        """
        async with self._sessionmaker() as session:
            stmt = select(WorkflowConfigModel).order_by(WorkflowConfigModel.created_at)
            if project_id is not None:
                stmt = stmt.where(WorkflowConfigModel.project_id == project_id)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, workflow_id: UUID, **fields: Any) -> Optional[WorkflowConfig]:
        """Update a workflow configuration's fields.

        Args:
            workflow_id (UUID): Id of the workflow configuration to update.
            **fields (Any): Fields to update; None values are ignored.

        Returns:
            Optional[WorkflowConfig]: The updated workflow
            configuration, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(WorkflowConfigModel, workflow_id)
            if not model:
                return None
            for key, value in fields.items():
                if value is not None:
                    setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def delete(self, workflow_id: UUID) -> bool:
        """Delete a workflow configuration.

        Args:
            workflow_id (UUID): Id of the workflow configuration to delete.

        Returns:
            bool: True if a config was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(WorkflowConfigModel, workflow_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
