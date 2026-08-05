"""SQLAlchemy implementation of ProjectRepositoryPort."""

from __future__ import annotations

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.project import Project
from ....domain.ports.outbound import ProjectRepositoryPort
from .models import ProjectModel


def _to_domain(model: ProjectModel) -> Project:
    """Convert a ProjectModel row into a Project domain object.

    Args:
        model (ProjectModel): The ORM row to convert.

    Returns:
        Project: The equivalent domain object.
    """
    return Project(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        slug=model.slug,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyProjectRepository(ProjectRepositoryPort):
    """Postgres-backed implementation of ProjectRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def create(self, *, tenant_id: UUID, name: str, slug: str) -> Project:
        """Insert a new project row.

        Args:
            tenant_id (UUID): Id of the owning tenant.
            name (str): Display name of the project.
            slug (str): Unique URL-safe identifier for the project.

        Returns:
            Project: The created project.
        """
        async with self._sessionmaker() as session:
            model = ProjectModel(tenant_id=tenant_id, name=name, slug=slug)
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_id(self, project_id: UUID) -> Optional[Project]:
        """Fetch a project by id.

        Args:
            project_id (UUID): Id of the project.

        Returns:
            Optional[Project]: The project, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(ProjectModel, project_id)
            return _to_domain(model) if model else None

    async def list_by_tenant(self, tenant_id: Optional[UUID] = None) -> List[Project]:
        """List projects, optionally filtered by tenant.

        Args:
            tenant_id (Optional[UUID]): If given, only return projects
                owned by this tenant.

        Returns:
            List[Project]: The matching projects, ordered by creation date.
        """
        async with self._sessionmaker() as session:
            stmt = select(ProjectModel).order_by(ProjectModel.created_at)
            if tenant_id is not None:
                stmt = stmt.where(ProjectModel.tenant_id == tenant_id)
            result = await session.execute(stmt)
            return [_to_domain(m) for m in result.scalars().all()]

    async def update(self, project_id: UUID, **fields: Any) -> Optional[Project]:
        """Update a project's fields.

        Args:
            project_id (UUID): Id of the project to update.
            **fields (Any): Fields to update; None values are ignored.

        Returns:
            Optional[Project]: The updated project, or None if it does
            not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(ProjectModel, project_id)
            if not model:
                return None
            for key, value in fields.items():
                if value is not None:
                    setattr(model, key, value)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def delete(self, project_id: UUID) -> bool:
        """Delete a project.

        Args:
            project_id (UUID): Id of the project to delete.

        Returns:
            bool: True if a project was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(ProjectModel, project_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
