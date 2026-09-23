"""Usage metering and cost rating.

Usage is recorded as plain QUANTITIES (messages per channel, LLM tokens,
messages processed by the platform); money is never stored with it. Cost
is computed when usage is read, by rating each quantity against a
versioned CostCatalog - so a rate added or corrected later applies to
usage already measured. Closing a billing period freezes the amounts
(see billing.py).

All money is in integer micro-units (1 EUR = 1_000_000), never floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

UsageKind = Literal["channel", "llm", "platform"]

MICROS_PER_UNIT = 1_000_000

# Units and SKUs used by the platform's own meters.
UNIT_MESSAGE = "message"
UNIT_INPUT_TOKEN = "input_token"
UNIT_OUTPUT_TOKEN = "output_token"
UNIT_CACHED_INPUT_TOKEN = "cached_input_token"
PLATFORM_PROVIDER = "flowsdone"
# One inbound message handled by an app (Langflow...): what plan quotas count.
SKU_AI_MESSAGE = "ai_message"

WILDCARD = "*"


class UsageEvent(BaseModel):
    """One measured quantity.

    `event_id` is deterministic (derived from its source: a message id,
    a Langfuse observation id...), so re-processing the same source never
    counts it twice.

    Attributes:
        event_id (UUID): Deterministic id of this measurement.
        timestamp (datetime): When the usage happened.
        tenant_id (UUID): Id of the tenant it is billed to.
        project_id (UUID): Id of the project.
        conversation_id (Optional[UUID]): Conversation it belongs to, if any.
        message_id (Optional[UUID]): Message it belongs to, if any.
        channel_type (str): Channel involved ("" if none).
        trace_id (str): Langfuse trace id, for LLM usage.
        kind (UsageKind): "channel", "llm" or "platform".
        provider (str): Who provides it ("whatsapp_evolution", "openai",
            "flowsdone"...).
        sku (str): What exactly (e.g. "message.outbound", a model name,
            "ai_message").
        quantity (Decimal): How much.
        unit (str): Unit of `quantity` ("message", "input_token"...).
    """

    event_id: UUID
    timestamp: datetime
    tenant_id: UUID
    project_id: UUID
    conversation_id: Optional[UUID] = None
    message_id: Optional[UUID] = None
    channel_type: str = ""
    trace_id: str = ""
    kind: UsageKind
    provider: str
    sku: str
    quantity: Decimal
    unit: str


class UsageAggregate(BaseModel):
    """Usage summed per day and meter - what rating works on.

    Attributes:
        day (date): Day (UTC) the usage happened.
        tenant_id (UUID): Tenant it is billed to.
        kind (UsageKind): Kind of usage.
        provider (str): Provider.
        channel_type (str): Channel ("" if none).
        sku (str): SKU.
        unit (str): Unit.
        quantity (Decimal): Total quantity that day.
    """

    day: date
    tenant_id: UUID
    kind: UsageKind
    provider: str
    channel_type: str = ""
    sku: str
    unit: str
    quantity: Decimal


class CostRate(BaseModel):
    """What Flowsdone pays for one meter, valid from a date on.

    A rate is never edited: a price change is a new rate with a later
    `valid_from`, so past usage keeps being rated with the price that
    applied when it happened.

    Attributes:
        id (UUID): Rate id (recorded as the price version on statements).
        kind (UsageKind): Kind of usage it prices.
        provider (str): Provider, or "*" for any.
        sku (str): Exact SKU, a prefix ending in "*" (e.g. "gpt-4.1-mini*"),
            or "*" for any.
        unit (str): Unit it prices.
        price_micros (int): Cost of `per_quantity` units, in micro-units.
        per_quantity (int): How many units `price_micros` is for (e.g.
            1_000_000 for "per million tokens").
        currency (str): Currency code.
        valid_from (datetime): From when it applies.
        note (Optional[str]): Free-form note (source of the price...).
        created_at (Optional[datetime]): When it was entered.
    """

    id: UUID
    kind: UsageKind
    provider: str
    sku: str
    unit: str
    price_micros: int
    per_quantity: int = 1
    currency: str = "EUR"
    valid_from: datetime
    note: Optional[str] = None
    created_at: Optional[datetime] = None

    def matches(self, *, kind: str, provider: str, sku: str, unit: str) -> bool:
        """Whether this rate prices the given meter.

        Args:
            kind (str): Kind of usage.
            provider (str): Provider.
            sku (str): SKU.
            unit (str): Unit.

        Returns:
            bool: True if kind and unit are equal and provider/sku match
            exactly, by prefix ("abc*") or by wildcard ("*").
        """
        if self.kind != kind or self.unit != unit:
            return False
        if self.provider not in (WILDCARD, provider):
            return False
        return _sku_matches(self.sku, sku)

    def specificity(self) -> tuple:
        """Sort key: the more specific rate wins among several matches.

        Returns:
            tuple: (exact provider, exact sku, prefix length).
        """
        exact_sku = not self.sku.endswith(WILDCARD)
        return (self.provider != WILDCARD, exact_sku, len(self.sku.rstrip(WILDCARD)))

    def cost_micros(self, quantity: Decimal) -> int:
        """Cost of a quantity at this rate, rounded to the micro-unit.

        Args:
            quantity (Decimal): Quantity in this rate's unit.

        Returns:
            int: Cost in micro-units.
        """
        value = Decimal(quantity) * Decimal(self.price_micros) / Decimal(self.per_quantity)
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _sku_matches(pattern: str, sku: str) -> bool:
    """Match a rate's SKU pattern against a SKU.

    Args:
        pattern (str): "*", "prefix*" or an exact SKU.
        sku (str): The SKU to test.

    Returns:
        bool: True on match.
    """
    if pattern == WILDCARD:
        return True
    if pattern.endswith(WILDCARD):
        return sku.startswith(pattern[:-1])
    return pattern == sku


@dataclass(frozen=True)
class RatedUsage:
    """A usage aggregate with its cost.

    Attributes:
        usage (UsageAggregate): The aggregate.
        rate (Optional[CostRate]): The rate applied, or None if no rate
            matches (the usage is "unrated": cost 0 until a rate is added).
        cost_micros (int): Cost in micro-units (0 if unrated).
    """

    usage: UsageAggregate
    rate: Optional[CostRate]
    cost_micros: int

    @property
    def rated(self) -> bool:
        """True when a rate was found."""
        return self.rate is not None


class CostCatalog:
    """All cost rates, able to find the one applying to a meter on a day."""

    def __init__(self, rates: Iterable[CostRate]) -> None:
        """Build the catalog.

        Args:
            rates (Iterable[CostRate]): Every rate, any order.
        """
        self._rates: List[CostRate] = list(rates)

    def find(self, *, kind: str, provider: str, sku: str, unit: str, at: datetime) -> Optional[CostRate]:
        """Find the rate for a meter at a moment: among the rates that
        match and are already valid, the most specific; among equally
        specific ones, the most recent `valid_from`.

        Args:
            kind (str): Kind of usage.
            provider (str): Provider.
            sku (str): SKU.
            unit (str): Unit.
            at (datetime): Moment the usage happened (timezone-aware).

        Returns:
            Optional[CostRate]: The rate, or None if none applies.
        """
        candidates = [
            r
            for r in self._rates
            if r.valid_from <= at and r.matches(kind=kind, provider=provider, sku=sku, unit=unit)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda r: (r.specificity(), r.valid_from))

    def rate(self, usage: UsageAggregate) -> RatedUsage:
        """Rate one daily aggregate, with the rate valid at the end of
        that day.

        Args:
            usage (UsageAggregate): The aggregate.

        Returns:
            RatedUsage: The aggregate and its cost.
        """
        at = datetime.combine(usage.day, time.max, tzinfo=timezone.utc)
        rate = self.find(kind=usage.kind, provider=usage.provider, sku=usage.sku, unit=usage.unit, at=at)
        return RatedUsage(usage=usage, rate=rate, cost_micros=rate.cost_micros(usage.quantity) if rate else 0)
