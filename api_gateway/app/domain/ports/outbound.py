"""Legacy outbound port module, superseded by the outbound/ package.

Since domain/ports/outbound/ exists as a package with an __init__.py,
Python resolves `from ...domain.ports.outbound import X` to that
package, not to this file. This module is unreachable and kept only
for historical reference; new outbound ports belong in the outbound/
package.
"""

from typing import Protocol

from api_gateway.app.application.dto.message_dto import MessageDTO


class MessagePublisherPort(Protocol):
    """Contract for publishing a message envelope to a message broker."""

    async def publish(self, message: MessageDTO) -> None:
        """Publish a message.

        Args:
            message (MessageDTO): The message DTO to publish.
        """
        ...


class LangflowExecutorPort(Protocol):
    """Contract for executing a Langflow workflow."""

    async def run(
        self,
        *,
        workflow_id: str,
        payload: dict,
        conversation_id: str,
    ) -> dict:
        """Run a Langflow workflow.

        Args:
            workflow_id (str): Id of the Langflow flow to execute.
            payload (dict): Input payload for the flow.
            conversation_id (str): Id of the conversation, used for
                session continuity in Langflow.

        Returns:
            dict: The raw response returned by Langflow.
        """
        ...
