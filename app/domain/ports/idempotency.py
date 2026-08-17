"""Port for idempotent workflow execution tracking."""

from typing import Protocol


class IdempotencyRepositoryPort(Protocol):
    """Tracks message processing state to prevent duplicate workflow runs."""

    async def try_start(self, message_id: str, workflow_id: str) -> bool:
        """Attempt to claim a message for processing.

        Args:
            message_id (str): Unique id of the message being processed.
            workflow_id (str): Id of the workflow that will process it.

        Returns:
            bool: True if this call claimed the message and processing
            should proceed; False if it was already claimed (duplicate).
        """
        ...

    async def mark_completed(self, message_id: str) -> None:
        """Mark a message as successfully processed.

        Args:
            message_id (str): Unique id of the message.
        """
        ...

    async def mark_failed(self, message_id: str) -> None:
        """Mark a message as failed so it can be retried.

        Args:
            message_id (str): Unique id of the message.
        """
        ...
