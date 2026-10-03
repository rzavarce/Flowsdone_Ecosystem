"""Postgres repositories for CRM integrations and handoffs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Collection, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.crypto import decrypt_credentials, encrypt_credentials
from app.adapters.outbound.db.errors import duplicate_as_already_exists
from app.adapters.outbound.db.models import CrmIntegrationModel, HandoffModel
from app.domain.models.crm import CrmIntegration, Handoff, HandoffCloseReason, HandoffStatus
from app.domain.ports.outbound import CrmIntegrationRepositoryPort, HandoffRepositoryPort


def _integration(model: CrmIntegrationModel) -> CrmIntegration:
    """Map a row to the domain model, decrypting its credentials.

    Args:
        model (CrmIntegrationModel): The row.

    Returns:
        CrmIntegration: The integration.
    """
    return CrmIntegration(
        id=model.id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        provider=model.provider,
        config=model.config or {},
        credentials=decrypt_credentials(model.credentials or {}),
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _handoff(model: HandoffModel) -> Handoff:
    """Map a row to the domain model.

    Args:
        model (HandoffModel): The row.

    Returns:
        Handoff: The handoff.
    """
    return Handoff(
        id=model.id,
        session_id=model.session_id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        integration_id=model.integration_id,
        provider=model.provider,
        channel_type=model.channel_type,
        contact=model.contact,
        status=model.status,
        reason=model.reason,
        external_ref=model.external_ref,
        opened_at=model.opened_at,
        closed_at=model.closed_at,
        close_reason=model.close_reason,
    )


class SqlAlchemyCrmIntegrationRepository(CrmIntegrationRepositoryPort):
    """Postgres-backed CrmIntegrationRepositoryPort (credentials encrypted)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def create(
        self,
        *,
        tenant_id: UUID,
        project_id: UUID,
        provider: str,
        config: Dict[str, Any],
        credentials: Dict[str, Any],
    ) -> CrmIntegration:
        """Insert a project's integration.

        Args:
            tenant_id (UUID): Owning tenant.
            project_id (UUID): Project it belongs to.
            provider (str): CRM provider.
            config (Dict[str, Any]): Non-secret settings.
            credentials (Dict[str, Any]): Secrets (encrypted at rest).

        Returns:
            CrmIntegration: The created integration.

        Raises:
            AlreadyExistsError: If the project already has one.
        """
        async with self._sessionmaker() as session:
            model = CrmIntegrationModel(
                tenant_id=tenant_id,
                project_id=project_id,
                provider=provider,
                config=config or {},
                credentials=encrypt_credentials(credentials or {}),
            )
            session.add(model)
            with duplicate_as_already_exists():
                await session.commit()
            await session.refresh(model)
            return _integration(model)

    async def get(self, integration_id: UUID) -> Optional[CrmIntegration]:
        """Fetch an integration by id.

        Args:
            integration_id (UUID): Integration id.

        Returns:
            Optional[CrmIntegration]: The integration, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(CrmIntegrationModel, integration_id)
            return _integration(model) if model else None

    async def get_for_project(self, project_id: UUID) -> Optional[CrmIntegration]:
        """Fetch a project's integration.

        Args:
            project_id (UUID): Project id.

        Returns:
            Optional[CrmIntegration]: The integration, or None.
        """
        async with self._sessionmaker() as session:
            model = (
                await session.execute(select(CrmIntegrationModel).where(CrmIntegrationModel.project_id == project_id))
            ).scalar_one_or_none()
            return _integration(model) if model else None

    async def list(self, *, tenant_ids: Optional[Collection[UUID]] = None) -> List[CrmIntegration]:
        """List integrations, oldest first.

        Args:
            tenant_ids (Optional[Collection[UUID]]): Only these tenants; None = all.

        Returns:
            List[CrmIntegration]: The integrations.
        """
        query = select(CrmIntegrationModel).order_by(CrmIntegrationModel.created_at)
        if tenant_ids is not None:
            if not tenant_ids:
                return []
            query = query.where(CrmIntegrationModel.tenant_id.in_(list(tenant_ids)))
        async with self._sessionmaker() as session:
            return [_integration(m) for m in (await session.execute(query)).scalars()]

    async def update(
        self,
        integration_id: UUID,
        *,
        config: Optional[Dict[str, Any]] = None,
        credentials: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[CrmIntegration]:
        """Update an integration; omitted fields are left untouched.

        Args:
            integration_id (UUID): Integration id.
            config (Optional[Dict[str, Any]]): New settings (replaced).
            credentials (Optional[Dict[str, Any]]): New secrets (replaced).
            status (Optional[str]): New status.

        Returns:
            Optional[CrmIntegration]: The updated integration, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(CrmIntegrationModel, integration_id)
            if model is None:
                return None
            if config is not None:
                model.config = config
            if credentials is not None:
                model.credentials = encrypt_credentials(credentials)
            if status is not None:
                model.status = status
            await session.commit()
            await session.refresh(model)
            return _integration(model)

    async def delete(self, integration_id: UUID) -> bool:
        """Delete an integration.

        Args:
            integration_id (UUID): Integration id.

        Returns:
            bool: True if it existed.
        """
        async with self._sessionmaker() as session:
            model = await session.get(CrmIntegrationModel, integration_id)
            if model is None:
                return False
            await session.delete(model)
            await session.commit()
            return True


class SqlAlchemyHandoffRepository(HandoffRepositoryPort):
    """Postgres-backed HandoffRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def open(self, handoff: Handoff) -> Handoff:
        """Insert an open handoff; if the session already has one, return it.

        Args:
            handoff (Handoff): The handoff to open.

        Returns:
            Handoff: The session's open handoff.
        """
        values = handoff.model_dump()
        statement = (
            insert(HandoffModel)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["session_id"], index_where=HandoffModel.status == "open")
        )
        async with self._sessionmaker() as session:
            await session.execute(statement)
            await session.commit()
        existing = await self.get_open(handoff.session_id)
        return existing or handoff

    async def get_open(self, session_id: str) -> Optional[Handoff]:
        """The open handoff of a conversation.

        Args:
            session_id (str): Switchboard session id.

        Returns:
            Optional[Handoff]: The open handoff, or None.
        """
        query = select(HandoffModel).where(HandoffModel.session_id == session_id, HandoffModel.status == "open")
        async with self._sessionmaker() as session:
            model = (await session.execute(query)).scalar_one_or_none()
            return _handoff(model) if model else None

    async def close(
        self, handoff_id: UUID, *, status: HandoffStatus, reason: HandoffCloseReason, at: datetime
    ) -> Optional[Handoff]:
        """End an open handoff (atomic: only one caller can end it).

        Args:
            handoff_id (UUID): Handoff id.
            status (HandoffStatus): "closed" or "expired".
            reason (HandoffCloseReason): Why it ended.
            at (datetime): When it ended.

        Returns:
            Optional[Handoff]: The ended handoff, or None if it was not open.
        """
        statement = (
            update(HandoffModel)
            .where(HandoffModel.id == handoff_id, HandoffModel.status == "open")
            .values(status=status, close_reason=reason, closed_at=at)
            .returning(HandoffModel)
        )
        async with self._sessionmaker() as session:
            model = (await session.execute(statement)).scalar_one_or_none()
            ended = _handoff(model) if model else None
            await session.commit()
            return ended
