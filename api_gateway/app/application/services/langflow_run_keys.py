"""Which Langflow API key a flow must be run with.

Every tenant has its own Langflow user (see LangflowAccount), and the flows
and global variables it builds in the editor belong to that user. Langflow
resolves a flow's variables for the owner of the API key that runs it, so
running every tenant's flow with the platform key fails with "<VAR>
variable not found" as soon as a flow uses a variable. Each flow is
therefore run with the key of the Langflow user that owns it:

    flow -> owner (asked to Langflow) -> tenant account -> its run key

The run key is created on first use - logging in as the tenant's user with
the password the gateway stores - and kept encrypted with the account.
Owners and keys are cached in memory: the lookup happens once per flow and
tenant per worker process, not on every message.

A flow whose owner is not a tenant's user (the platform superuser), or a
lookup that fails, falls back to the platform key: exactly what happened
before, so this never makes a run fail that used to work.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Optional, Tuple
from uuid import UUID

from app.domain.ports.outbound import LangflowAccountRepositoryPort, LangflowAdminPort

logger = logging.getLogger("langflow.run_keys")

RUN_KEY_NAME = "flowsdone-runner"
_OWNER_TTL_SECONDS = 600.0


class LangflowRunKeys:
    """Resolves (and lazily creates) the key each flow is run with."""

    def __init__(
        self,
        *,
        admin: LangflowAdminPort,
        accounts: LangflowAccountRepositoryPort,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the resolver.

        Args:
            admin (LangflowAdminPort): Langflow client (flow owner, login, key creation).
            accounts (LangflowAccountRepositoryPort): Tenant -> Langflow user accounts.
            clock (Callable[[], float]): Monotonic clock (tests).
        """
        self._admin = admin
        self._accounts = accounts
        self._clock = clock
        self._owners: Dict[str, Tuple[Optional[str], float]] = {}
        self._keys: Dict[str, str] = {}

    async def key_for(self, workflow_id: str) -> Optional[str]:
        """The key to run `workflow_id` with.

        Args:
            workflow_id (str): The Langflow flow.

        Returns:
            Optional[str]: The owner tenant's key, or None to use the
            platform key (owner isn't a tenant, or the lookup failed).
        """
        try:
            owner = await self._owner(workflow_id)
            if owner is None:
                return None
            if owner in self._keys:
                return self._keys[owner]
            account = await self._accounts.get_by_langflow_user_id(owner)
            if account is None:
                return None
            key = account.run_api_key.get_secret_value() if account.run_api_key else None
            if not key:
                key = await self._create_key(account.tenant_id, account.username, account.password.get_secret_value())
            self._keys[owner] = key
            return key
        except Exception:
            logger.warning("langflow.run_keys.resolve_failed", extra={"workflow_id": workflow_id}, exc_info=True)
            return None

    async def replace_key(self, workflow_id: str) -> Optional[str]:
        """Create a fresh key for the flow's tenant, dropping the cached one.

        For when Langflow refuses the stored key (someone deleted it in the
        editor's settings).

        Args:
            workflow_id (str): The Langflow flow whose run was refused.

        Returns:
            Optional[str]: The new key, or None if it couldn't be created.
        """
        owner = self._owners.get(workflow_id, (None, 0.0))[0]
        self._keys.pop(owner or "", None)
        try:
            if owner is None:
                return None
            account = await self._accounts.get_by_langflow_user_id(owner)
            if account is None:
                return None
            key = await self._create_key(account.tenant_id, account.username, account.password.get_secret_value())
            self._keys[owner] = key
            return key
        except Exception:
            logger.warning("langflow.run_keys.replace_failed", extra={"workflow_id": workflow_id}, exc_info=True)
            return None

    async def _owner(self, workflow_id: str) -> Optional[str]:
        """Owner of a flow, cached for a while (ownership rarely changes).

        Args:
            workflow_id (str): The Langflow flow.

        Returns:
            Optional[str]: The owner's Langflow user id, or None.
        """
        cached = self._owners.get(workflow_id)
        now = self._clock()
        if cached and now - cached[1] < _OWNER_TTL_SECONDS:
            return cached[0]
        owner = await self._admin.flow_owner(workflow_id)
        self._owners[workflow_id] = (owner, now)
        return owner

    async def _create_key(self, tenant_id: UUID, username: str, password: str) -> str:
        """Log in as the tenant's user, create its run key and store it.

        Args:
            tenant_id (UUID): The tenant.
            username (str): Its Langflow login name.
            password (str): Its Langflow password.

        Returns:
            str: The new key.
        """
        tokens = await self._admin.login(username, password)
        key = await self._admin.create_api_key(tokens.access_token, RUN_KEY_NAME)
        await self._accounts.set_run_api_key(tenant_id, key)
        logger.info("langflow.run_keys.created", extra={"tenant_id": str(tenant_id)})
        return key
