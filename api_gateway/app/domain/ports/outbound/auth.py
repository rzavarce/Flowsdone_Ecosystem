"""Ports for console authentication: users, password hashing, server-side
sessions and login throttling.
"""

from __future__ import annotations

from typing import List, Optional, Protocol
from uuid import UUID

from app.domain.models.user import User, UserCredentials


class UserAlreadyExistsError(Exception):
    """Raised by `UserRepositoryPort.create` when the email is taken."""


class UserRepositoryPort(Protocol):
    """Persistence contract for users and their tenant memberships."""

    async def create(
        self,
        *,
        email: str,
        name: str,
        role: str,
        password_hash: str,
        tenant_ids: List[UUID],
    ) -> User:
        """Create a user.

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
        ...

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Fetch a user by id.

        Args:
            user_id (UUID): Id of the user.

        Returns:
            Optional[User]: The user, or None if it does not exist.
        """
        ...

    async def get_credentials_by_email(self, email: str) -> Optional[UserCredentials]:
        """Fetch a user with its password hash, for verifying a login.

        Args:
            email (str): Email to look up (matched case-insensitively).

        Returns:
            Optional[UserCredentials]: The user and hash, or None if no
            user has that email.
        """
        ...

    async def mark_login(self, user_id: UUID) -> None:
        """Record a successful sign-in (sets `last_login_at` to now).

        Args:
            user_id (UUID): Id of the user.
        """
        ...

    async def list(self) -> List[User]:
        """List all users, ordered by creation date.

        Returns:
            List[User]: Every user (without password hashes).
        """
        ...

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
        """Update a user. `None` means "leave unchanged".

        Args:
            user_id (UUID): Id of the user.
            name (Optional[str]): New display name.
            role (Optional[str]): New role.
            status (Optional[str]): `active` or `disabled`.
            tenant_ids (Optional[List[UUID]]): If given, REPLACES the user's
                tenant memberships (an empty list removes them all).
            password_hash (Optional[str]): New password hash.

        Returns:
            Optional[User]: The updated user, or None if it does not exist.
        """
        ...

    async def delete(self, user_id: UUID) -> bool:
        """Delete a user and its memberships.

        Args:
            user_id (UUID): Id of the user.

        Returns:
            bool: True if a user was deleted, False if it did not exist.
        """
        ...


class PasswordHasherPort(Protocol):
    """Contract for hashing and verifying passwords."""

    def hash(self, password: str) -> str:
        """Hash a password with a fresh random salt.

        Args:
            password (str): The plaintext password.

        Returns:
            str: A self-describing hash (algorithm, parameters, salt and
            digest), safe to store.
        """
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """Check a password against a stored hash in constant time.

        Args:
            password (str): The plaintext password to check.
            password_hash (str): A hash previously returned by `hash`.

        Returns:
            bool: True if it matches. A malformed hash yields False.
        """
        ...


class AuthSessionRepositoryPort(Protocol):
    """Server-side sessions identified by an opaque token.

    Unlike a signed JWT, a session can be revoked at any time (logout,
    disabled user) and reflects role/tenant changes immediately.
    """

    async def create(self, user_id: UUID, *, ttl_seconds: int) -> str:
        """Open a session.

        Args:
            user_id (UUID): Owner of the session.
            ttl_seconds (int): Idle lifetime; refreshed by `touch`.

        Returns:
            str: The opaque token to hand to the client. It is not
            recoverable from storage.
        """
        ...

    async def get_user_id(self, token: str, *, ttl_seconds: int) -> Optional[UUID]:
        """Resolve a token to its user and slide the expiry forward.

        Args:
            token (str): Token presented by the client.
            ttl_seconds (int): New idle lifetime.

        Returns:
            Optional[UUID]: The owner, or None if the token is unknown or
            expired.
        """
        ...

    async def delete(self, token: str) -> None:
        """Close a session (idempotent).

        Args:
            token (str): Token to invalidate.
        """
        ...

    async def delete_all_for_user(self, user_id: UUID) -> None:
        """Close every session of a user (e.g. after a password change).

        Args:
            user_id (UUID): Owner whose sessions are closed.
        """
        ...


class LoginThrottlePort(Protocol):
    """Failed-login counters used to slow down brute-force attempts."""

    async def failures(self, key: str) -> int:
        """Current failure count for a key.

        Args:
            key (str): Bucket key (e.g. `email:<addr>` or `ip:<addr>`).

        Returns:
            int: Failures recorded in the active window (0 if none).
        """
        ...

    async def record_failure(self, key: str, *, window_seconds: int) -> int:
        """Count a failure; the window starts at the first failure.

        Args:
            key (str): Bucket key.
            window_seconds (int): Window after which the count resets.

        Returns:
            int: The new failure count.
        """
        ...

    async def reset(self, key: str) -> None:
        """Clear a bucket (after a successful login).

        Args:
            key (str): Bucket key.
        """
        ...
