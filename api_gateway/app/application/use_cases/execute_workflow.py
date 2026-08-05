"""Use case for running a Langflow workflow idempotently."""

import logging

from ...domain.models.message_envelope import MessageEnvelope
from ...domain.ports.idempotency import IdempotencyRepositoryPort
from ...domain.ports.outbound import LangflowExecutorPort

logger = logging.getLogger("usecase.execute_workflow")


class ExecuteWorkflowUseCase:
    """Executes a Langflow workflow in an idempotent way, given a
    MessageEnvelope as input.
    """

    def __init__(
        self,
        executor: LangflowExecutorPort,
        idempotency_repo: IdempotencyRepositoryPort,
    ) -> None:
        """Build the use case.

        Args:
            executor (LangflowExecutorPort): Executor used to run the
                Langflow flow.
            idempotency_repo (IdempotencyRepositoryPort): Repository
                used to prevent duplicate execution.
        """
        self.executor = executor
        self.idempotency_repo = idempotency_repo

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

            result = await self.executor.run(
                workflow_id=meta.workflow_id,
                payload=envelope.payload,
                conversation_id=meta.conversation_id,
            )

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
