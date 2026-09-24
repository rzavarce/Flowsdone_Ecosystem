"""Use case for deleting a tenant with everything that only exists for it.

The database cascade already takes the tenant's projects, agents, channels
and memberships. Two things outlive it otherwise:

- its `client` account: the email stays registered, so the tenant cannot be
  created again with it ("already exists");
- its Langflow user, with all its folders and flows: a new tenant with the
  same slug would inherit them.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.application.use_cases.manage_users import DeleteUserUseCase
from app.domain.ports.outbound import LangflowAccountRepositoryPort, LangflowAdminPort, TenantRepositoryPort, UserRepositoryPort

logger = logging.getLogger("usecase.delete_tenant")


class DeleteTenantUseCase:
    """Deletes a tenant, its client accounts and its Langflow user.

    Langflow goes first: if it fails, nothing is deleted. Only `client`
    users that belong to this tenant alone are deleted; staff keep their
    account (they just lose the membership, by cascade).
    """

    def __init__(
        self,
        *,
        tenant_repo: TenantRepositoryPort,
        user_repo: UserRepositoryPort,
        delete_user: DeleteUserUseCase,
        accounts: LangflowAccountRepositoryPort,
        langflow: LangflowAdminPort,
    ) -> None:
        """Build the use case.

        Args:
            tenant_repo (TenantRepositoryPort): Tenants.
            user_repo (UserRepositoryPort): Finds the tenant's client accounts.
            delete_user (DeleteUserUseCase): Deletes them (and closes their sessions).
            accounts (LangflowAccountRepositoryPort): The tenant's Langflow user.
            langflow (LangflowAdminPort): Deletes that user.
        """
        self._tenants = tenant_repo
        self._users = user_repo
        self._delete_user = delete_user
        self._accounts = accounts
        self._langflow = langflow

    async def execute(self, tenant_id: UUID) -> bool:
        """Delete the tenant (the caller has already checked it may).

        Args:
            tenant_id (UUID): The tenant.

        Returns:
            bool: True if it was deleted, False if it did not exist.

        Raises:
            LangflowSessionError: If Langflow fails (nothing is deleted).
        """
        if await self._tenants.get_by_id(tenant_id) is None:
            return False
        account = await self._accounts.get(tenant_id)
        if account is not None and account.langflow_user_id:
            await self._langflow.delete_user(account.langflow_user_id)
            logger.info("tenant.langflow_user_deleted", extra={"tenant_id": str(tenant_id)})
        for user in await self._users.list():
            if user.role == "client" and list(user.tenant_ids) == [tenant_id]:
                await self._delete_user.execute(user.id)
        return await self._tenants.delete(tenant_id)
