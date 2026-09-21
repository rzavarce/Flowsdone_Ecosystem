"""Use cases for administering console users (update, delete)."""

from __future__ import annotations

import asyncio
from typing import List, Optional
from uuid import UUID

from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH
from app.domain.models.user import USER_ROLES, User
from app.domain.ports.outbound import (
    AuthSessionRepositoryPort,
    PasswordHasherPort,
    TenantRepositoryPort,
    UserRepositoryPort,
)

__all__ = ["DeleteUserUseCase", "SelfLockoutError", "UpdateUserUseCase"]

_STATUSES = ("active", "disabled")


class SelfLockoutError(Exception):
    """An admin tried to remove their own access (delete, disable or demote
    themselves), which could leave the platform without an administrator."""


class UpdateUserUseCase:
    """Edits a user, keeping the same invariants as creation and closing the
    user's sessions whenever something that affects their access changes
    (role, tenants, status, password), so a change is effective immediately
    instead of when their session happens to expire.
    """

    def __init__(
        self,
        *,
        user_repo: UserRepositoryPort,
        tenant_repo: TenantRepositoryPort,
        hasher: PasswordHasherPort,
        sessions: AuthSessionRepositoryPort,
    ) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Loads and persists the user.
            tenant_repo (TenantRepositoryPort): Validates tenant ids.
            hasher (PasswordHasherPort): Hashes a new password.
            sessions (AuthSessionRepositoryPort): Closes the user's sessions.
        """
        self._users = user_repo
        self._tenants = tenant_repo
        self._hasher = hasher
        self._sessions = sessions

    async def execute(
        self,
        user_id: UUID,
        *,
        actor_id: Optional[UUID] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        tenant_ids: Optional[List[UUID]] = None,
        password: Optional[str] = None,
    ) -> Optional[User]:
        """Update a user.

        Args:
            user_id (UUID): User to edit.
            actor_id (Optional[UUID]): Who is making the change (None for the
                API key); used to stop admins locking themselves out.
            name (Optional[str]): New display name.
            role (Optional[str]): New role.
            status (Optional[str]): `active` or `disabled`.
            tenant_ids (Optional[List[UUID]]): New memberships (replaces all).
            password (Optional[str]): New plaintext password.

        Returns:
            Optional[User]: The updated user, or None if it does not exist.

        Raises:
            SelfLockoutError: If `actor_id == user_id` and the change would
                disable or demote them.
            ValueError: On an invalid role, status, name, password or tenants.
        """
        current = await self._users.get_by_id(user_id)
        if current is None:
            return None

        if name is not None and not name.strip():
            raise ValueError("name is required")
        if role is not None and role not in USER_ROLES:
            raise ValueError(f"role must be one of: {', '.join(USER_ROLES)}")
        if status is not None and status not in _STATUSES:
            raise ValueError(f"status must be one of: {', '.join(_STATUSES)}")
        if password is not None and len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

        if actor_id is not None and actor_id == user_id:
            if status == "disabled" or (role is not None and role != "admin"):
                raise SelfLockoutError("you cannot disable or demote yourself")

        final_role = role or current.role
        if final_role == "admin":
            tenant_ids = [] if (tenant_ids is not None or role == "admin") else None
        else:
            final_tenants = tenant_ids if tenant_ids is not None else current.tenant_ids
            if not final_tenants:
                raise ValueError(f"role '{final_role}' needs at least one tenant")
            if tenant_ids is not None:
                found = {t.id for t in await self._tenants.list_by_ids(tenant_ids)}
                missing = [str(t) for t in tenant_ids if t not in found]
                if missing:
                    raise ValueError(f"unknown tenant id(s): {', '.join(missing)}")

        password_hash = (
            await asyncio.to_thread(self._hasher.hash, password) if password is not None else None
        )
        updated = await self._users.update(
            user_id,
            name=name.strip() if name is not None else None,
            role=role,
            status=status,
            tenant_ids=tenant_ids,
            password_hash=password_hash,
        )

        # Only close sessions when access really changed: re-sending the same
        # values (or just renaming) must not log the person out.
        access_changed = (
            (role is not None and role != current.role)
            or (status is not None and status != current.status)
            or (tenant_ids is not None and set(tenant_ids) != set(current.tenant_ids))
            or password_hash is not None
        )
        if updated is not None and access_changed:
            await self._sessions.delete_all_for_user(user_id)
        return updated


class DeleteUserUseCase:
    """Deletes a user and closes their sessions."""

    def __init__(self, *, user_repo: UserRepositoryPort, sessions: AuthSessionRepositoryPort) -> None:
        """Build the use case.

        Args:
            user_repo (UserRepositoryPort): Persistence.
            sessions (AuthSessionRepositoryPort): Closes the user's sessions.
        """
        self._users = user_repo
        self._sessions = sessions

    async def execute(self, user_id: UUID, *, actor_id: Optional[UUID] = None) -> bool:
        """Delete a user.

        Args:
            user_id (UUID): User to delete.
            actor_id (Optional[UUID]): Who is deleting (None for the API key).

        Returns:
            bool: True if deleted, False if the user did not exist.

        Raises:
            SelfLockoutError: If an admin tries to delete themselves.
        """
        if actor_id is not None and actor_id == user_id:
            raise SelfLockoutError("you cannot delete yourself")
        deleted = await self._users.delete(user_id)
        if deleted:
            await self._sessions.delete_all_for_user(user_id)
        return deleted
