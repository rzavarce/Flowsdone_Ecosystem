from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.workflow_config import WorkflowConfig
from ....domain.ports.outbound import WorkflowConfigRepositoryPort
from .models import WorkflowConfigModel


def _to_domain(model: WorkflowConfigModel) -> WorkflowConfig:
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
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
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
        async with self._sessionmaker() as session:
            model = await session.get(WorkflowConfigModel, workflow_id)
            return _to_domain(model) if model else None

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[WorkflowConfig]:
        async with self._sessionmaker() as session:
            stmt = select(WorkflowConfigModel).order_by(WorkflowConfigModel.created_at)
            if project_id is not None:
                stmt = stmt.where(WorkflowConfigModel.project_id == project_id)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, workflow_id: UUID, **fields: Any) -> Optional[WorkflowConfig]:
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
        async with self._sessionmaker() as session:
            model = await session.get(WorkflowConfigModel, workflow_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
