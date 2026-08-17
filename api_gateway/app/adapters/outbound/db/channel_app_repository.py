"""SQLAlchemy implementation of ChannelAppRepositoryPort."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api_gateway.app.domain.models.channel_app import ChannelApp
from api_gateway.app.domain.ports.outbound import ChannelAppRepositoryPort
from api_gateway.app.adapters.outbound.db.crypto import decrypt_credentials, encrypt_credentials
from api_gateway.app.adapters.outbound.db.models import ChannelAppModel


def _to_domain(model: ChannelAppModel) -> ChannelApp:
    """Convert a ChannelAppModel row into a ChannelApp domain object,
    decrypting its credentials.

    Args:
        model (ChannelAppModel): The ORM row to convert.

    Returns:
        ChannelApp: The equivalent domain object.
    """
    return ChannelApp(
        id=model.id,
        provider=model.provider,
        credentials=decrypt_credentials(model.credentials),
        config=model.config,
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyChannelAppRepository(ChannelAppRepositoryPort):
    """Postgres-backed implementation of ChannelAppRepositoryPort.

    Credentials are encrypted with Fernet before being persisted (see
    crypto.py) and decrypted on read.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    async def upsert(self, *, provider: str, credentials: dict, config: dict) -> ChannelApp:
        """Create or replace the shared app credentials for a provider.

        Args:
            provider (str): Provider identifier (e.g. "meta", "twitter",
                "tiktok").
            credentials (dict): App credentials to encrypt and store.
            config (dict): Arbitrary app configuration.

        Returns:
            ChannelApp: The upserted channel app.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ChannelAppModel).where(ChannelAppModel.provider == provider)
            )
            model = result.scalar_one_or_none()

            if model is None:
                model = ChannelAppModel(
                    provider=provider,
                    credentials=encrypt_credentials(credentials or {}),
                    config=config or {},
                )
                session.add(model)
            else:
                model.credentials = encrypt_credentials(credentials or {})
                model.config = config or {}

            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def get_by_provider(self, provider: str) -> Optional[ChannelApp]:
        """Fetch the active app credentials for a provider.

        Args:
            provider (str): Provider identifier.

        Returns:
            Optional[ChannelApp]: The channel app, or None if it does
            not exist or is inactive.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ChannelAppModel).where(
                    ChannelAppModel.provider == provider,
                    ChannelAppModel.status == "active",
                )
            )
            model = result.scalar_one_or_none()
            return _to_domain(model) if model else None

    async def list(self) -> List[ChannelApp]:
        """List all provider app credential records, ordered by provider.

        Returns:
            List[ChannelApp]: All existing channel app records.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ChannelAppModel).order_by(ChannelAppModel.provider)
            )
            return [_to_domain(m) for m in result.scalars().all()]

    async def delete(self, provider: str) -> bool:
        """Delete a provider's app credentials.

        Args:
            provider (str): Provider identifier.

        Returns:
            bool: True if a record was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ChannelAppModel).where(ChannelAppModel.provider == provider)
            )
            model = result.scalar_one_or_none()
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True
