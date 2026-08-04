from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ....domain.models.channel_app import ChannelApp
from ....domain.ports.outbound import ChannelAppRepositoryPort
from .crypto import decrypt_credentials, encrypt_credentials
from .models import ChannelAppModel


def _to_domain(model: ChannelAppModel) -> ChannelApp:
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
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def upsert(self, *, provider: str, credentials: dict, config: dict) -> ChannelApp:
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
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(ChannelAppModel).order_by(ChannelAppModel.provider)
            )
            return [_to_domain(m) for m in result.scalars().all()]

    async def delete(self, provider: str) -> bool:
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
