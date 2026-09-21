"""Helpers shared by the authentication use cases."""

from __future__ import annotations

from app.application.dto.auth_dto import AuthenticatedUser, TenantRef
from app.domain.models.user import User
from app.domain.ports.outbound import TenantRepositoryPort


async def build_authenticated_user(user: User, tenant_repo: TenantRepositoryPort) -> AuthenticatedUser:
    """Resolve a user's tenants into the DTO the console consumes.

    Args:
        user (User): The signed-in user.
        tenant_repo (TenantRepositoryPort): Used to load tenant names.

    Returns:
        AuthenticatedUser: `admin` gets every tenant; other roles only
        the ones they are a member of.
    """
    if user.role == "admin":
        tenants = await tenant_repo.list()
    else:
        tenants = await tenant_repo.list_by_ids(user.tenant_ids)
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        tenants=[TenantRef(id=t.id, name=t.name) for t in tenants],
    )
