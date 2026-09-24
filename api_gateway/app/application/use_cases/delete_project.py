"""Use case for deleting a project together with its Langflow folder.

Each project is mirrored by a folder in its tenant's Langflow (see
`langflow_sso.py`). Deleting only the gateway project would leave that folder,
and its flows, behind in the editor; this removes both.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.application.use_cases.langflow_sso import PrepareLangflowSessionUseCase
from app.domain.ports.outbound import LangflowAccountRepositoryPort, LangflowAdminPort, ProjectRepositoryPort

logger = logging.getLogger("usecase.delete_project")


class DeleteProjectUseCase:
    """Deletes a project and, first, its folder (with its flows) in Langflow.

    Langflow goes first: if it fails, nothing is deleted, so the editor is
    never left with a folder the console no longer knows about. A project
    whose folder was never created (its tenant never opened the editor) is
    deleted without touching Langflow.
    """

    def __init__(
        self,
        *,
        project_repo: ProjectRepositoryPort,
        accounts: LangflowAccountRepositoryPort,
        workspace: PrepareLangflowSessionUseCase,
        langflow: LangflowAdminPort,
    ) -> None:
        """Build the use case.

        Args:
            project_repo (ProjectRepositoryPort): Projects.
            accounts (LangflowAccountRepositoryPort): Project -> Langflow folder.
            workspace (PrepareLangflowSessionUseCase): Logs in as the tenant's Langflow user.
            langflow (LangflowAdminPort): Deletes the folder.
        """
        self._projects = project_repo
        self._accounts = accounts
        self._workspace = workspace
        self._langflow = langflow

    async def execute(self, project_id: UUID) -> bool:
        """Delete the project (the caller has already checked its scope).

        Args:
            project_id (UUID): The project.

        Returns:
            bool: True if it was deleted, False if it did not exist.

        Raises:
            LangflowSessionError: If Langflow fails (the project is kept).
            LangflowTargetNotFoundError: If the project's tenant is gone.
        """
        project = await self._projects.get_by_id(project_id)
        if project is None:
            return False
        # Read before deleting: the project -> folder row goes away with the project.
        folder_id = await self._accounts.get_folder(project_id)
        if folder_id is not None:
            workspace = await self._workspace.open_workspace(project.tenant_id)
            # Opening the workspace recreates folders deleted by hand in the
            # editor, so the one to delete is the one it reports now.
            folder_id = workspace.folders.get(project_id, folder_id)
            await self._langflow.delete_project(workspace.tokens.access_token, folder_id)
            logger.info("project.langflow_folder_deleted", extra={"project_id": str(project_id), "folder_id": folder_id})
        return await self._projects.delete(project_id)
