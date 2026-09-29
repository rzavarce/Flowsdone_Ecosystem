"""Use case for running a Langflow workflow idempotently."""

import logging
from typing import Optional

from app.application.services.langflow_run_keys import LangflowRunKeys
from app.domain.models.message_envelope import MessageEnvelope
from app.domain.ports.idempotency import IdempotencyRepositoryPort
from app.domain.ports.outbound import LangflowExecutorPort

logger = logging.getLogger("usecase.execute_workflow")

# Langflow's answer when the API key is unknown or was deleted.
_KEY_REFUSED = (401, 403)


class ExecuteWorkflowUseCase:
    """Executes a Langflow workflow in an idempotent way, given a
    MessageEnvelope as input.
    """

    def __init__(
        self,
        executor: LangflowExecutorPort,
        idempotency_repo: IdempotencyRepositoryPort,
        run_keys: Optional[LangflowRunKeys] = None,
    ) -> None:
        """Build the use case.

        Args:
            executor (LangflowExecutorPort): Executor used to run the
                Langflow flow.
            idempotency_repo (IdempotencyRepositoryPort): Repository
                used to prevent duplicate execution.
            run_keys (Optional[LangflowRunKeys]): Picks the key each flow
                runs with (its owner tenant's, so its global variables
                resolve). None runs everything with the platform key.
        """
        self.executor = executor
        self.idempotency_repo = idempotency_repo
        self.run_keys = run_keys

    async def execute(self, envelope: MessageEnvelope) -> dict | None:
        """Run the workflow for an inbound envelope, skipping duplicates.

        Args:
            envelope (MessageEnvelope): The inbound envelope to process.

        Returns:
            dict | None: The raw Langflow result, or None if the
            message was already claimed by a previous (duplicate) call.

        Raises:
            Exception: Re-raises any error from the executor after
                marking the message as failed, so it can be retried.
        """
        meta = envelope.meta

        started = await self.idempotency_repo.try_start(
            message_id=meta.message_id,
            workflow_id=meta.workflow_id,
        )

        if not started:
            logger.warning(
                "workflow.execution.skipped.duplicate",
                extra={
                    "message_id": str(meta.message_id),
                    "workflow_id": str(meta.workflow_id),
                },
            )
            return None

        try:
            logger.info(
                "workflow.execution.started",
                extra={
                    "message_id": str(meta.message_id),
                    "workflow_id": str(meta.workflow_id),
                    "conversation_id": str(meta.conversation_id),
                },
            )

            result = await self._run(envelope)

            await self.idempotency_repo.mark_completed(meta.message_id)

            logger.info(
                "workflow.execution.completed",
                extra={"message_id": str(meta.message_id)},
            )

            return result

        except Exception:
            await self.idempotency_repo.mark_failed(meta.message_id)
            logger.exception("workflow.execution.failed")
            raise

    async def _run(self, envelope: MessageEnvelope) -> dict | None:
        """Run the envelope's flow with its owner's key.

        If Langflow refuses a tenant key (deleted from the editor), a new
        one is created and the run is tried once more.

        Args:
            envelope (MessageEnvelope): The inbound envelope to process.

        Returns:
            dict | None: The raw Langflow result.
        """
        meta = envelope.meta
        api_key = await self.run_keys.key_for(meta.workflow_id) if self.run_keys else None

        async def run(key: Optional[str]) -> dict | None:
            return await self.executor.run(
                workflow_id=meta.workflow_id,
                payload=envelope.payload,
                # Scopes Langflow's memory (and Langfuse's session) to
                # the Conversation, not to the contact forever.
                conversation_id=meta.effective_llm_session_id(),
                api_key=key,
            )

        try:
            return await run(api_key)
        except Exception as exc:
            if not (api_key and self.run_keys and getattr(exc, "status_code", None) in _KEY_REFUSED):
                raise
            logger.warning("workflow.execution.run_key_refused", extra={"workflow_id": str(meta.workflow_id)})
            new_key = await self.run_keys.replace_key(meta.workflow_id)
            if not new_key:
                raise
            return await run(new_key)
