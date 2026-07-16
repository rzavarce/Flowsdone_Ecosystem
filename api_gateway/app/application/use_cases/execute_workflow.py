import logging

from ...domain.models.message_envelope import MessageEnvelope
from ...domain.ports.outbound import LangflowExecutorPort
from ...domain.ports.idempotency import IdempotencyRepositoryPort

logger = logging.getLogger("usecase.execute_workflow")


class ExecuteWorkflowUseCase:
    """
    Executes a Langflow workflow in an idempotent way
    using a MessageEnvelope as input.
    """

    def __init__(
        self,
        executor: LangflowExecutorPort,
        idempotency_repo: IdempotencyRepositoryPort,
    ) -> None:
        self.executor = executor
        self.idempotency_repo = idempotency_repo

    async def execute(self, envelope: MessageEnvelope) -> dict | None:
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
