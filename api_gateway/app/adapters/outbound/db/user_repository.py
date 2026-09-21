"""SQLAlchemy implementation of UserRepositoryPort."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.outbound.db.models import UserModel, UserTenantModel
from app.domain.models.user import User, UserCredentials
from app.domain.ports.outbound import UserAlreadyExistsError, UserRepositoryPort


def _to_domain(model: UserModel, tenant_ids: List[UUID]) -> User:
    """Convert a UserModel row plus its memberships into a User.

    Args:
        model (UserModel): The ORM row.
        tenant_ids (List[UUID]): Tenants the user belongs to.

    Returns:
        User: The equivalent domain object (without the password hash).
    """
    return User(
        id=model.id,
        email=model.email,
        name=model.name,
        role=model.role,  # type: ignore[arg-type]
        status=model.status,  # type: ignore[arg-type]
        tenant_ids=tenant_ids,
        last_login_at=model.last_login_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyUserRepository(UserRepositoryPort):
    """Postgres-backed implementation of UserRepositoryPort."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        """Build the repository.

        Args:
            sessionmaker (async_sessionmaker[AsyncSession]): Session
                factory used to open database sessions.
        """
        self._sessionmaker = sessionmaker

    @staticmethod
    async def _tenant_ids(session: AsyncSession, user_ids: List[UUID]) -> Dict[UUID, List[UUID]]:
        """Load memberships for several users in one query.

        Args:
            session (AsyncSession): Open session.
            user_ids (List[UUID]): Users to load memberships for.

        Returns:
            Dict[UUID, List[UUID]]: user id -> tenant ids (empty list if none).
        """
        grouped: Dict[UUID, List[UUID]] = {uid: [] for uid in user_ids}
        if not user_ids:
            return grouped
        rows = await session.execute(
            select(UserTenantModel.user_id, UserTenantModel.tenant_id)
            .where(UserTenantModel.user_id.in_(user_ids))
            .order_by(UserTenantModel.created_at)
        )
        for user_id, tenant_id in rows.all():
            grouped[user_id].append(tenant_id)
        return grouped

    async def create(
        self,
        *,
        email: str,
        name: str,
        role: str,
        password_hash: str,
        tenant_ids: List[UUID],
    ) -> User:
        """Insert a user and its tenant memberships atomically.

        Args:
            email (str): Lowercase email (unique, case-insensitively).
            name (str): Display name.
            role (str): One of `USER_ROLES`.
            password_hash (str): Hash produced by `PasswordHasherPort.hash`.
            tenant_ids (List[UUID]): Tenants the user belongs to.

        Returns:
            User: The created user.

        Raises:
            UserAlreadyExistsError: If the email is already registered.
        """
        async with self._sessionmaker() as session:
            model = UserModel(email=email, name=name, role=role, password_hash=password_hash)
            session.add(model)
            try:
                await session.flush()
                for tenant_id in dict.fromkeys(tenant_ids):
                    session.add(UserTenantModel(user_id=model.id, tenant_id=tenant_id))
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                if "uq_users_email_lower" in str(exc.orig):
                    raise UserAlreadyExistsError(email) from exc
                raise
            await session.refresh(model)
            return _to_domain(model, list(dict.fromkeys(tenant_ids)))

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch a user by id.

        Args:
            user_id (UUID): Id of the user.

        Returns:
            Optional[User]: The user, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(UserModel, user_id)
            if not model:
                return None
            tenants = await self._tenant_ids(session, [model.id])
            return _to_domain(model, tenants[model.id])

    async def get_credentials_by_email(self, email: str) -> Optional[UserCredentials]:
        """Fetch a user with its password hash, for verifying a login.

        Args:
            email (str): Email to look up (matched case-insensitively).

        Returns:
            Optional[UserCredentials]: The user and hash, or None if no
            user has that email.
        """
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(UserModel).where(func.lower(UserModel.email) == email.lower())
            )
            model = result.scalar_one_or_none()
            if not model:
                return None
            tenants = await self._tenant_ids(session, [model.id])
            return UserCredentials(
                user=_to_domain(model, tenants[model.id]),
                password_hash=model.password_hash,
            )

    async def list(self) -> List[User]:
        """List all users, ordered by creation date.

        Returns:
            List[User]: Every user (without password hashes).
        """
        async with self._sessionmaker() as session:
            result = await session.execute(select(UserModel).order_by(UserModel.created_at))
            models = result.scalars().all()
            tenants = await self._tenant_ids(session, [m.id for m in models])
            return [_to_domain(m, tenants[m.id]) for m in models]

    async def update(
        self,
        user_id: UUID,
        *,
        name: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        tenant_ids: Optional[List[UUID]] = None,
        password_hash: Optional[str] = None,
    ) -> Optional[User]:
        """Update a user; `tenant_ids`, when given, replaces the memberships.

        Args:
            user_id (UUID): Id of the user.
            name (Optional[str]): New display name.
            role (Optional[str]): New role.
            status (Optional[str]): `active` or `disabled`.
            tenant_ids (Optional[List[UUID]]): New memberships (replaces all).
            password_hash (Optional[str]): New password hash.

        Returns:
            Optional[User]: The updated user, or None if it does not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(UserModel, user_id)
            if not model:
                return None
            for field, value in (
                ("name", name),
                ("role", role),
                ("status", status),
                ("password_hash", password_hash),
            ):
                if value is not None:
                    setattr(model, field, value)
            if tenant_ids is not None:
                await session.execute(delete(UserTenantModel).where(UserTenantModel.user_id == user_id))
                for tenant_id in dict.fromkeys(tenant_ids):
                    session.add(UserTenantModel(user_id=user_id, tenant_id=tenant_id))
            await session.commit()
            await session.refresh(model)
            memberships = await self._tenant_ids(session, [user_id])
            return _to_domain(model, memberships[user_id])

    async def delete(self, user_id: UUID) -> bool:
        """Delete a user (memberships go with it via ON DELETE CASCADE).

        Args:
            user_id (UUID): Id of the user.

        Returns:
            bool: True if a user was deleted, False if it did not exist.
        """
        async with self._sessionmaker() as session:
            model = await session.get(UserModel, user_id)
            if not model:
                return False
            await session.delete(model)
            await session.commit()
            return True

    async def mark_login(self, user_id: UUID) -> None:
        """Record a successful sign-in (sets `last_login_at` to now).

        Args:
            user_id (UUID): Id of the user.
        """
        async with self._sessionmaker() as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(last_login_at=datetime.now(timezone.utc))
            )
            await session.commit()
