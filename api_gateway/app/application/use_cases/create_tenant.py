"""Use case: create a tenant together with its `client` user."""

from __future__ import annotations

from app.application.use_cases.provision_user import ProvisionUserUseCase
from app.domain.models.tenant import Tenant
from app.domain.ports.outbound import TenantRepositoryPort, UserAlreadyExistsError, UserRepositoryPort

__all__ = ["CreateTenantUseCase"]


class CreateTenantUseCase:
    """Creates a tenant and provisions its `client` user in one step.

    A tenant is the client's own workspace, so it always ships with a
    `client` account for them - created `pending`, activated by the same
    email flow as any other user (see `ProvisionUserUseCase`). The email is
    checked against existing users *before* creating the tenant: `tenant_repo`
    and `user_repo` are separate Postgres sessions with no shared
    transaction, so this ordering avoids the most likely way to end up with
    a tenant that has no client (a duplicate email) - it does not protect
    against an infrastructure failure between the two `create()` calls,
    which is a known, accepted gap for this use case.
    """

    def __init__(
        self,
        *,
        tenant_repo: TenantRepositoryPort,
        user_repo: UserRepositoryPort,
        provision_user: ProvisionUserUseCase,
    ) -> None:
        """Build the use case.

        Args:
            tenant_repo (TenantRepositoryPort): Persists the tenant.
            user_repo (UserRepositoryPort): Checked up-front for the email
                clash (see class docstring).
            provision_user (ProvisionUserUseCase): Creates the pending
                `client` user and sends their activation email.
        """
        self._tenants = tenant_repo
        self._users = user_repo
        self._provision_user = provision_user

    async def execute(self, *, name: str, slug: str, client_email: str, client_name: str) -> Tenant:
        """Create the tenant and its client user.

        Args:
            name (str): Tenant display name.
            slug (str): Tenant URL-safe unique identifier.
            client_email (str): Login email for the tenant's `client` user.
            client_name (str): Display name for that user.

        Returns:
            Tenant: The created tenant.

        Raises:
            UserAlreadyExistsError: If `client_email` is already registered.
            ValueError: If `client_email`/`client_name` are invalid (see
                `CreateUserUseCase`).
            EmailSendError: If the tenant was created but the activation
                email could not be sent - the tenant and its client user
                both exist; retry via the resend-activation endpoint.
        """
        existing = await self._users.get_credentials_by_email(client_email)
        if existing is not None:
            raise UserAlreadyExistsError(client_email)

        tenant = await self._tenants.create(name=name, slug=slug)
        await self._provision_user.execute(
            email=client_email,
            name=client_name,
            role="client",
            tenant_ids=[tenant.id],
        )
        return tenant
