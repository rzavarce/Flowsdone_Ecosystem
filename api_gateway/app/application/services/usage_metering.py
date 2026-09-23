"""Turns platform activity into usage quantities (UsageEvent).

Pure functions, no I/O: callers decide where the events go. Event ids
are deterministic (uuid5 of their source), so re-processing a message or
a Langfuse observation never counts it twice.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import NAMESPACE_URL, UUID, uuid5

from app.domain.models.conversation import Conversation
from app.domain.models.conversation_message import ConversationMessageRecorded
from app.domain.models.usage import (
    PLATFORM_PROVIDER,
    SKU_AI_MESSAGE,
    UNIT_CACHED_INPUT_TOKEN,
    UNIT_INPUT_TOKEN,
    UNIT_MESSAGE,
    UNIT_OUTPUT_TOKEN,
    UsageEvent,
)
from app.domain.ports.outbound import LlmGeneration

_NAMESPACE = uuid5(NAMESPACE_URL, "https://flowsdone.com/usage")

# Model name prefix -> provider. Only used to label usage; rates can
# still match any provider with "*".
_PROVIDER_PREFIXES = (
    (("gpt-", "o1", "o3", "o4", "chatgpt", "text-embedding", "whisper", "tts-"), "openai"),
    (("claude",), "anthropic"),
    (("gemini", "gemma"), "google"),
    (("mistral", "mixtral", "codestral", "ministral"), "mistral"),
    (("llama", "meta-llama"), "meta"),
    (("command",), "cohere"),
    (("deepseek",), "deepseek"),
)


def usage_event_id(source: str, meter: str) -> UUID:
    """Deterministic id of a usage event.

    Args:
        source (str): Id of what produced it (message id, observation id...).
        meter (str): Which meter of that source (a source may yield several).

    Returns:
        UUID: The same UUID for the same (source, meter), always.
    """
    return uuid5(_NAMESPACE, f"{source}/{meter}")


def infer_llm_provider(model: str) -> str:
    """Guess the LLM provider from a model name.

    Args:
        model (str): Model name as reported by the tracing system.

    Returns:
        str: Provider name, or "unknown".
    """
    name = model.lower().split("/")[-1]
    for prefixes, provider in _PROVIDER_PREFIXES:
        if name.startswith(prefixes):
            return provider
    return "unknown"


def usage_from_message(event: ConversationMessageRecorded) -> List[UsageEvent]:
    """Usage produced by one recorded message.

    Every message is one unit of its channel ("message.inbound"/
    "message.outbound", priced per channel). An inbound, billable message
    from the contact is also one platform "ai_message" - what plan quotas
    count.

    Args:
        event (ConversationMessageRecorded): The message.

    Returns:
        List[UsageEvent]: One or two events.
    """
    common = dict(
        timestamp=event.timestamp,
        tenant_id=event.tenant_id,
        project_id=event.project_id,
        conversation_id=event.conversation_id,
        message_id=event.message_id,
        channel_type=event.channel_type,
        quantity=Decimal(1),
        unit=UNIT_MESSAGE,
    )
    events = [
        UsageEvent(
            event_id=usage_event_id(str(event.message_id), "channel"),
            kind="channel",
            provider=event.channel_type,
            sku=f"message.{event.direction}",
            **common,
        )
    ]
    if event.direction == "inbound" and event.sender_type == "contact" and event.billable:
        events.append(
            UsageEvent(
                event_id=usage_event_id(str(event.message_id), "platform"),
                kind="platform",
                provider=PLATFORM_PROVIDER,
                sku=SKU_AI_MESSAGE,
                **common,
            )
        )
    return events


def usage_from_generation(generation: LlmGeneration, conversation: Conversation) -> List[UsageEvent]:
    """Usage produced by one LLM call, attributed to its conversation.

    Args:
        generation (LlmGeneration): The call.
        conversation (Conversation): The conversation its trace belongs to.

    Returns:
        List[UsageEvent]: One event per non-zero token counter.
    """
    provider = infer_llm_provider(generation.model)
    counters = (
        (UNIT_INPUT_TOKEN, generation.input_tokens),
        (UNIT_OUTPUT_TOKEN, generation.output_tokens),
        (UNIT_CACHED_INPUT_TOKEN, generation.cached_input_tokens),
    )
    return [
        UsageEvent(
            event_id=usage_event_id(generation.id, unit),
            timestamp=generation.start_time,
            tenant_id=conversation.tenant_id,
            project_id=conversation.project_id,
            conversation_id=conversation.id,
            channel_type=conversation.channel_type,
            trace_id=generation.trace_id,
            kind="llm",
            provider=provider,
            sku=generation.model,
            quantity=Decimal(count),
            unit=unit,
        )
        for unit, count in counters
        if count
    ]
