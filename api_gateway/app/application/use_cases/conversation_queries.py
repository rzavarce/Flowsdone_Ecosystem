"""Read side of conversations: one conversation with its transcript and
what it cost."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from app.domain.models.conversation import Conversation
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.models.usage import (
    UNIT_CACHED_INPUT_TOKEN,
    UNIT_INPUT_TOKEN,
    UNIT_OUTPUT_TOKEN,
    CostCatalog,
    RatedUsage,
)
from app.domain.ports.outbound import (
    ConversationRepositoryPort,
    CostRateRepositoryPort,
    MessageArchivePort,
    UsageStorePort,
)


@dataclass(frozen=True)
class ConversationDetail:
    """A conversation, its messages and its cost.

    Attributes:
        conversation (Conversation): The conversation record.
        messages (List[ConversationMessageRecorded]): Transcript, oldest
            first (empty once past the archive's retention).
        usage (List[RatedUsage]): Its usage, rated.
        cost_micros (int): Total cost (channel + LLM).
        llm_input_tokens (int): Non-cached input tokens.
        llm_output_tokens (int): Output tokens.
        llm_cached_input_tokens (int): Cached input tokens.
    """

    conversation: Conversation
    messages: List[ConversationMessageRecorded]
    usage: List[RatedUsage]
    cost_micros: int
    llm_input_tokens: int
    llm_output_tokens: int
    llm_cached_input_tokens: int


class GetConversationDetailUseCase:
    """Loads a conversation with its transcript (archive) and rated usage."""

    def __init__(
        self,
        *,
        conversations: ConversationRepositoryPort,
        archive: MessageArchivePort,
        usage_store: UsageStorePort,
        cost_rates: CostRateRepositoryPort,
    ) -> None:
        """Build the use case.

        Args:
            conversations (ConversationRepositoryPort): Conversation records.
            archive (MessageArchivePort): Message archive.
            usage_store (UsageStorePort): Usage archive.
            cost_rates (CostRateRepositoryPort): Cost catalog.
        """
        self._conversations = conversations
        self._archive = archive
        self._usage = usage_store
        self._rates = cost_rates

    async def execute(self, conversation_id: UUID, *, message_limit: int = 500) -> Optional[ConversationDetail]:
        """Load the detail.

        Args:
            conversation_id (UUID): Conversation id.
            message_limit (int): Maximum messages returned.

        Returns:
            Optional[ConversationDetail]: The detail, or None if the
            conversation does not exist (scope is checked by the caller,
            with `conversation.tenant_id`).
        """
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            return None
        messages = await self._archive.list_messages(
            tenant_id=conversation.tenant_id, conversation_id=conversation_id, limit=message_limit
        )
        catalog = CostCatalog(await self._rates.list_all())
        rated = [
            catalog.rate(row)
            for row in await self._usage.aggregate_conversation(
                tenant_id=conversation.tenant_id, conversation_id=conversation_id
            )
        ]

        def tokens(unit: str) -> int:
            return sum(int(r.usage.quantity) for r in rated if r.usage.kind == "llm" and r.usage.unit == unit)

        return ConversationDetail(
            conversation=conversation,
            messages=messages,
            usage=rated,
            cost_micros=sum(r.cost_micros for r in rated),
            llm_input_tokens=tokens(UNIT_INPUT_TOKEN),
            llm_output_tokens=tokens(UNIT_OUTPUT_TOKEN),
            llm_cached_input_tokens=tokens(UNIT_CACHED_INPUT_TOKEN),
        )
