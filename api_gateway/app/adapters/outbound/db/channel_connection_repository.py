from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.channel_connection import ChannelConnection
from ....domain.models.channel_resolution import ChannelResolution
from ....domain.ports.outbound import ChannelConnectionRepositoryPort
from .crypto import decrypt_credentials, encrypt_credentials
from .models import AgentModel, ChannelConnectionModel, ProjectModel


def _to_domain(model: ChannelConnectionModel) -> ChannelConnection:
    return ChannelConnection(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        channel_type=model.channel_type,
        external_id=model.external_id,
        display_name=model.display_name,
        credentials=decrypt_credentials(model.credentials),
        config=model.config,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyChannelConnectionRepository(ChannelConnectionRepositoryPort):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

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
        async with self._sessionmaker() as session:
            model = ChannelConnectionModel(
                project_id=project_id,
                agent_id=agent_id,
                channel_type=channel_type,
                external_id=external_id,
                display_name=display_name,
                credentials=encrypt_credentials(credentials or {}),
                config=config or {},
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, channel_connection_id: UUID) -> Optional[ChannelConnection]:
        async with self._sessionmaker() as session:
            model = await session.get(ChannelConnectionModel, channel_connection_id)
            return _to_domain(model) if model else None

    async def get_by_channel_and_external_id(
        self, channel_type: str, external_id: str
    ) -> Optional[ChannelResolution]:
        async with self._sessionmaker() as session:
            stmt = (
                select(ChannelConnectionModel, AgentModel, ProjectModel)
                .join(AgentModel, AgentModel.id == ChannelConnectionModel.agent_id)
                .join(ProjectModel, ProjectModel.id == ChannelConnectionModel.project_id)
                .where(
                    ChannelConnectionModel.channel_type == channel_type,
                    ChannelConnectionModel.external_id == external_id,
                    ChannelConnectionModel.status == "active",
                    AgentModel.status == "active",
                    ProjectModel.status == "active",
                )
            )
            result = await session.execute(stmt)
            row = result.first()
            if not row:
                return None

            connection, agent, project = row
            return ChannelResolution(
                tenant_id=project.tenant_id,
                project_id=project.id,
                agent_id=agent.id,
                langflow_flow_id=agent.langflow_flow_id,
                channel_connection_id=connection.id,
                channel_type=connection.channel_type,
                credentials=decrypt_credentials(connection.credentials),
            )

    async def list_by_project(self, project_id: Optional[UUID] = None) -> List[ChannelConnection]:
        async with self._sessionmaker() as session:
            stmt = select(ChannelConnectionModel).order_by(ChannelConnectionModel.created_at)
            if project_id is not None:
                stmt = stmt.where(ChannelConnectionModel.project_id == project_id)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, channel_connection_id: UUID, **fields: Any) -> Optional[ChannelConnection]:
        async with self._sessionmaker() as session:
            model = await session.get(ChannelConnectionModel, channel_connection_id)
            if not model:
                return None

            credentials = fields.pop("credentials", None)
            if credentials is not None:
                model.credentials = encrypt_credentials(credentials)

            for key, value in fields.items():
                if value is not None:
                    setattr(model, key, value)

            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def delete(self, channel_connection_id: UUID) -> bool:
        async with self._sessionmaker() as session:
            model = await session.get(ChannelConnectionModel, channel_connection_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
