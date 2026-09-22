"""SQLAlchemy implementation of LangflowAccountRepositoryPort."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.crypto import decrypt_credentials, encrypt_credentials
from app.adapters.outbound.db.errors import duplicate_as_already_exists
from app.adapters.outbound.db.models import LangflowAccountModel, LangflowFolderModel
from app.domain.models.langflow_account import LangflowAccount
from app.domain.ports.outbound import LangflowAccountRepositoryPort


def _to_domain(model: LangflowAccountModel) -> LangflowAccount:
    """Convert a row into a LangflowAccount, decrypting the password.

    Args:
        model (LangflowAccountModel): The ORM row.

    Returns:
        LangflowAccount: The domain object.
    """
    return LangflowAccount(
        tenant_id=model.tenant_id,
        username=model.username,
        password=decrypt_credentials(model.credentials).get("password", ""),
        langflow_user_id=model.langflow_user_id,
        created_at=model.created_at,
    )


class SqlAlchemyLangflowAccountRepository(LangflowAccountRepositoryPort):
    """Postgres-backed tenant -> Langflow user and project -> folder mapping."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def get(self, tenant_id: UUID) -> Optional[LangflowAccount]:
        """Fetch a tenant's Langflow account.

        Args:
            tenant_id (UUID): The tenant.

        Returns:
            Optional[LangflowAccount]: The account, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(LangflowAccountModel, tenant_id)
            return _to_domain(model) if model else None

    async def create(self, *, tenant_id: UUID, username: str, password: str) -> LangflowAccount:
        """Store a new account with its password encrypted.

        Args:
            tenant_id (UUID): The tenant.
            username (str): Langflow login name.
            password (str): Plain password (encrypted before it is stored).

        Returns:
            LangflowAccount: The stored account.

        Raises:
            AlreadyExistsError: If the tenant (or the username) already has one.
        """
        async with self._sessionmaker() as session:
            model = LangflowAccountModel(
                tenant_id=tenant_id, username=username, credentials=encrypt_credentials({"password": password})
            )
            session.add(model)
            with duplicate_as_already_exists():
                await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def set_langflow_user_id(self, tenant_id: UUID, langflow_user_id: str) -> None:
        """Record the id Langflow gave the user.

        Args:
            tenant_id (UUID): The tenant.
            langflow_user_id (str): Id of the user inside Langflow.
        """
        async with self._sessionmaker() as session:
            await session.execute(
                update(LangflowAccountModel)
                .where(LangflowAccountModel.tenant_id == tenant_id)
                .values(langflow_user_id=langflow_user_id)
            )
            await session.commit()

    async def get_folder(self, project_id: UUID) -> Optional[str]:
        """Langflow folder id of a project.

        Args:
            project_id (UUID): The gateway project.

        Returns:
            Optional[str]: The folder id, or None.
        """
        async with self._sessionmaker() as session:
            model = await session.get(LangflowFolderModel, project_id)
            return model.folder_id if model else None

    async def save_folder(self, project_id: UUID, folder_id: str) -> None:
        """Record (or replace) a project's Langflow folder.

        Args:
            project_id (UUID): The gateway project.
            folder_id (str): The Langflow folder id.
        """
        stmt = insert(LangflowFolderModel).values(project_id=project_id, folder_id=folder_id)
        stmt = stmt.on_conflict_do_update(index_elements=["project_id"], set_={"folder_id": folder_id})
        async with self._sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()
