"""SQLAlchemy implementation of WebchatShareLinkRepositoryPort."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.crypto import decrypt_credentials, encrypt_credentials
from app.adapters.outbound.db.models import WebchatShareLinkModel
from app.domain.models.webchat_share_link import WebchatShareLink
from app.domain.ports.outbound import WebchatShareLinkRepositoryPort


def _to_domain(model: WebchatShareLinkModel) -> WebchatShareLink:
    """Convert a row into a WebchatShareLink, decrypting its token.

    Args:
        model (WebchatShareLinkModel): The ORM row.

    Returns:
        WebchatShareLink: The domain object.
    """
    return WebchatShareLink(
        id=model.id,
        agent_id=model.agent_id,
        token=decrypt_credentials(model.credentials).get("token", ""),
        created_by=model.created_by,
        created_at=model.created_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
    )


class SqlAlchemyWebchatShareLinkRepository(WebchatShareLinkRepositoryPort):
    """Postgres-backed share links."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session factory.
        """
        self._sessionmaker = sessionmaker

    async def create(
        self,
        *,
        agent_id: UUID,
        token: str,
        token_hash: str,
        created_by: Optional[UUID],
        expires_at: Optional[datetime],
    ) -> WebchatShareLink:
        """Store a new link with its token encrypted.

        Args:
            agent_id (UUID): The agent it opens.
            token (str): The secret in the URL.
            token_hash (str): SHA-256 of the token.
            created_by (Optional[UUID]): Console user who created it.
            expires_at (Optional[datetime]): Expiry; None = never.

        Returns:
            WebchatShareLink: The stored link.
        """
        async with self._sessionmaker() as session:
            model = WebchatShareLinkModel(
                agent_id=agent_id,
                token_hash=token_hash,
                credentials=encrypt_credentials({"token": token}),
                created_by=created_by,
                expires_at=expires_at,
            )
            session.add(model)
            await session.commit()
            await session.refresh(model)
            return _to_domain(model)

    async def list_by_agent(self, agent_id: UUID) -> List[WebchatShareLink]:
        """Unrevoked links of an agent, newest first.

        Args:
            agent_id (UUID): The agent.

        Returns:
            List[WebchatShareLink]: Its links.
        """
        async with self._sessionmaker() as session:
            rows = await session.execute(
                select(WebchatShareLinkModel)
                .where(WebchatShareLinkModel.agent_id == agent_id, WebchatShareLinkModel.revoked_at.is_(None))
                .order_by(WebchatShareLinkModel.created_at.desc())
            )
            return [_to_domain(model) for model in rows.scalars()]

    async def get_by_token_hash(self, token_hash: str) -> Optional[WebchatShareLink]:
        """Find a link by the hash of its token.

        Args:
            token_hash (str): SHA-256 of the token.

        Returns:
            Optional[WebchatShareLink]: The link, or None.
        """
        async with self._sessionmaker() as session:
            model = (
                await session.execute(
                    select(WebchatShareLinkModel).where(WebchatShareLinkModel.token_hash == token_hash)
                )
            ).scalar_one_or_none()
            return _to_domain(model) if model else None

    async def revoke(self, agent_id: UUID, share_id: UUID, now: datetime) -> bool:
        """Revoke one of an agent's links.

        Args:
            agent_id (UUID): The agent.
            share_id (UUID): The link.
            now (datetime): Revocation time.

        Returns:
            bool: False if the agent has no such unrevoked link.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                update(WebchatShareLinkModel)
                .where(
                    WebchatShareLinkModel.id == share_id,
                    WebchatShareLinkModel.agent_id == agent_id,
                    WebchatShareLinkModel.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await session.commit()
            return result.rowcount > 0
