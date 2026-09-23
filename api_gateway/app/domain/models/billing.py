"""Plans, subscriptions, quota decisions and monthly statements.

What a tenant is charged: a fixed monthly fee that includes a number of
AI-handled messages per channel, plus overage for messages beyond it,
priced per channel. Overage prices are set by the admin, usually from the
suggestion "average cost per message x (1 + margin)" (see
PricingInsight). LLM tokens are not billed directly: their cost is
inside the message price; a plan may cap models and token use as fair use.

All money is in integer micro-units (1 EUR = 1_000_000), never floats.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Literal, Optional, Sequence
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.usage import (
    SKU_AI_MESSAGE,
    UNIT_CACHED_INPUT_TOKEN,
    UNIT_INPUT_TOKEN,
    UNIT_OUTPUT_TOKEN,
    WILDCARD,
    RatedUsage,
)

OverageMode = Literal["notify", "overage", "hard_stop"]
StatementStatus = Literal["preview", "closed"]

# Share of the included messages at which an alert is sent (once per
# tenant, channel and month).
ALERT_THRESHOLDS_PCT = (80, 100)


class Plan(BaseModel):
    """A commercial plan.

    Attributes:
        id (UUID): Plan id.
        code (str): Short unique code ("starter", "pro"...).
        name (str): Display name.
        description (Optional[str]): Free text.
        monthly_fee_micros (int): Fixed monthly fee.
        currency (str): Currency code.
        included_messages (Dict[str, int]): AI-handled messages included
            per month, per channel type; "*" applies to channels not listed.
        overage_price_micros (Dict[str, int]): Price of each message beyond
            the included ones, per channel type; "*" for unlisted channels.
            A channel with no price here has unpriced overage (only
            possible in "notify" mode in practice).
        margin_pct (Decimal): Target margin over cost, used to suggest
            overage prices (30 = +30%).
        allowed_models (List[str]): LLM model patterns the plan allows
            ("gpt-4.1-mini*"); empty = any. Checked against usage, not
            enforced inside Langflow.
        monthly_token_allowance (Optional[int]): Fair-use LLM tokens per
            month (input+output); None = unlimited. Exceeding it raises a
            flag for the admin, never blocks.
        default_overage_mode (OverageMode): What happens past the quota
            unless the subscription overrides it.
        active (bool): Inactive plans can't be assigned to new subscriptions.
        created_at (Optional[datetime]): Creation time.
        updated_at (Optional[datetime]): Last update.
    """

    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    monthly_fee_micros: int = 0
    currency: str = "EUR"
    included_messages: Dict[str, int] = Field(default_factory=dict)
    overage_price_micros: Dict[str, int] = Field(default_factory=dict)
    margin_pct: Decimal = Decimal(30)
    allowed_models: List[str] = Field(default_factory=list)
    monthly_token_allowance: Optional[int] = None
    default_overage_mode: OverageMode = "notify"
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def included_for(self, channel_type: str) -> int:
        """Included messages for a channel.

        Args:
            channel_type (str): Channel type.

        Returns:
            int: The channel's allowance, else the "*" one, else 0.
        """
        return self.included_messages.get(channel_type, self.included_messages.get(WILDCARD, 0))

    def overage_price_for(self, channel_type: str) -> Optional[int]:
        """Price of one message beyond the quota on a channel.

        Args:
            channel_type (str): Channel type.

        Returns:
            Optional[int]: Micro-units, or None if not priced.
        """
        return self.overage_price_micros.get(channel_type, self.overage_price_micros.get(WILDCARD))

    def allows_model(self, model: str) -> bool:
        """Whether the plan allows an LLM model.

        Args:
            model (str): Model name as reported.

        Returns:
            bool: True if no restriction or a pattern matches.
        """
        if not self.allowed_models:
            return True
        return any(
            model.startswith(p[:-1]) if p.endswith(WILDCARD) else model == p for p in self.allowed_models
        )


class TenantSubscription(BaseModel):
    """Which plan a tenant is on, with its per-tenant overrides.

    Attributes:
        tenant_id (UUID): Tenant id.
        plan_id (UUID): Plan id.
        overage_mode (Optional[OverageMode]): Overrides the plan's default.
        spending_cap_micros (Optional[int]): Maximum overage per month in
            "overage" mode; past it, messages are refused. None = no cap.
        started_at (datetime): When the subscription started.
        updated_at (Optional[datetime]): Last change.
    """

    tenant_id: UUID
    plan_id: UUID
    overage_mode: Optional[OverageMode] = None
    spending_cap_micros: Optional[int] = None
    started_at: datetime
    updated_at: Optional[datetime] = None

    def effective_mode(self, plan: Plan) -> OverageMode:
        """The overage mode in force.

        Args:
            plan (Plan): The subscribed plan.

        Returns:
            OverageMode: The override, or the plan's default.
        """
        return self.overage_mode or plan.default_overage_mode


@dataclass(frozen=True)
class QuotaDecision:
    """Whether one more AI-handled message is admitted.

    Attributes:
        allowed (bool): Hand the message to the app or not.
        reason (str): "no_subscription", "within_quota", "overage",
            "notify", "hard_stop" or "spending_cap".
        channel_type (str): Channel of the message.
        used (int): Messages used this month on the channel, including
            this one if allowed.
        included (int): Included messages on the channel.
        overage_spend_micros (int): Overage spent this month (all
            channels), including this message if allowed.
        thresholds_crossed (tuple): Alert thresholds (% of included) this
            message crossed.
    """

    allowed: bool
    reason: str
    channel_type: str
    used: int = 0
    included: int = 0
    overage_spend_micros: int = 0
    thresholds_crossed: tuple = ()


def overage_spend(plan: Plan, used_by_channel: Dict[str, int]) -> int:
    """Overage spent across channels for given usage.

    Args:
        plan (Plan): The plan.
        used_by_channel (Dict[str, int]): Messages used per channel.

    Returns:
        int: Micro-units (unpriced channels count 0).
    """
    total = 0
    for channel, used in used_by_channel.items():
        over = max(0, used - plan.included_for(channel))
        total += over * (plan.overage_price_for(channel) or 0)
    return total


def evaluate_quota(
    plan: Plan,
    subscription: TenantSubscription,
    channel_type: str,
    used_by_channel: Dict[str, int],
) -> QuotaDecision:
    """Decide on one more message, given this month's usage BEFORE it.

    Args:
        plan (Plan): The subscribed plan.
        subscription (TenantSubscription): The subscription.
        channel_type (str): Channel of the new message.
        used_by_channel (Dict[str, int]): Messages already used this month
            per channel (not counting the new one).

    Returns:
        QuotaDecision: The decision, with the usage as it would be after it.
    """
    included = plan.included_for(channel_type)
    before = used_by_channel.get(channel_type, 0)
    after = before + 1
    after_usage = {**used_by_channel, channel_type: after}
    spend_after = overage_spend(plan, after_usage)
    crossed = _thresholds_crossed(before, after, included)

    def decision(allowed: bool, reason: str) -> QuotaDecision:
        return QuotaDecision(
            allowed=allowed,
            reason=reason,
            channel_type=channel_type,
            used=after if allowed else before,
            included=included,
            overage_spend_micros=spend_after if allowed else overage_spend(plan, used_by_channel),
            thresholds_crossed=crossed if allowed else (),
        )

    if after <= included:
        return decision(True, "within_quota")
    mode = subscription.effective_mode(plan)
    if mode == "hard_stop":
        return decision(False, "hard_stop")
    if mode == "notify":
        return decision(True, "notify")
    cap = subscription.spending_cap_micros
    if cap is not None and spend_after > cap:
        return decision(False, "spending_cap")
    return decision(True, "overage")


def _thresholds_crossed(before: int, after: int, included: int) -> tuple:
    """Alert thresholds crossed going from `before` to `after` messages.

    Args:
        before (int): Usage before the message.
        after (int): Usage after it.
        included (int): Included messages.

    Returns:
        tuple: Threshold percentages crossed (empty if none included).
    """
    if included <= 0:
        return ()
    return tuple(t for t in ALERT_THRESHOLDS_PCT if before * 100 < t * included <= after * 100)


def month_bounds(period: str) -> tuple[datetime, datetime]:
    """UTC start (inclusive) and end (exclusive) of a "YYYY-MM" period.

    Args:
        period (str): e.g. "2026-09".

    Returns:
        tuple[datetime, datetime]: The month's bounds.

    Raises:
        ValueError: If `period` is not "YYYY-MM".
    """
    year, month = (int(part) for part in period.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + (month == 12), month % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def period_of(moment: datetime) -> str:
    """The "YYYY-MM" period a moment falls in (UTC).

    Args:
        moment (datetime): The moment.

    Returns:
        str: The period.
    """
    return moment.astimezone(timezone.utc).strftime("%Y-%m")


class StatementChannelLine(BaseModel):
    """Messages and charges of one channel in a statement.

    Attributes:
        channel_type (str): Channel type.
        messages (int): AI-handled messages.
        included (int): Included by the plan.
        overage_messages (int): Messages beyond the included ones.
        overage_price_micros (Optional[int]): Price per overage message.
        overage_amount_micros (int): Overage charged.
        cost_micros (int): What those messages cost Flowsdone (channel +
            LLM usage on this channel).
    """

    channel_type: str
    messages: int
    included: int
    overage_messages: int
    overage_price_micros: Optional[int]
    overage_amount_micros: int
    cost_micros: int


class StatementCostLine(BaseModel):
    """Cost of one meter in a statement.

    Attributes:
        kind (str): "channel", "llm" or "platform".
        provider (str): Provider.
        sku (str): SKU.
        unit (str): Unit.
        channel_type (str): Channel ("" if none).
        quantity (Decimal): Quantity used.
        cost_micros (int): Its cost (0 if unrated).
        rated (bool): False if it is external usage with no rate (platform
            meters without a rate count as rated at 0).
    """

    kind: str
    provider: str
    sku: str
    unit: str
    channel_type: str = ""
    quantity: Decimal
    cost_micros: int
    rated: bool


class BillingStatement(BaseModel):
    """A tenant's charges and costs for one month.

    Attributes:
        tenant_id (UUID): Tenant id.
        period (str): "YYYY-MM".
        status (StatementStatus): "preview" (live, recomputed on read) or
            "closed" (frozen).
        currency (str): Currency code.
        plan_id (Optional[UUID]): Plan billed (None without subscription).
        plan_code (Optional[str]): Its code at the time.
        plan_name (Optional[str]): Its name at the time.
        overage_mode (Optional[str]): Mode in force.
        monthly_fee_micros (int): Plan fee.
        channels (List[StatementChannelLine]): Per-channel messages/charges.
        costs (List[StatementCostLine]): Per-meter costs.
        overage_amount_micros (int): Total overage.
        revenue_micros (int): Fee + overage.
        cost_micros (int): Total cost.
        margin_micros (int): Revenue - cost.
        margin_pct (Optional[Decimal]): Margin over revenue, in %.
        llm_input_tokens (int): Non-cached input tokens.
        llm_output_tokens (int): Output tokens.
        llm_cached_input_tokens (int): Cached input tokens.
        token_allowance (Optional[int]): The plan's fair-use tokens.
        over_token_allowance (bool): input+output above the allowance.
        disallowed_models (List[str]): Models used that the plan doesn't allow.
        unrated_meters (int): Meters with usage but no rate (cost 0).
        generated_at (datetime): When it was computed.
    """

    tenant_id: UUID
    period: str
    status: StatementStatus = "preview"
    currency: str = "EUR"
    plan_id: Optional[UUID] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    overage_mode: Optional[str] = None
    monthly_fee_micros: int = 0
    channels: List[StatementChannelLine] = Field(default_factory=list)
    costs: List[StatementCostLine] = Field(default_factory=list)
    overage_amount_micros: int = 0
    revenue_micros: int = 0
    cost_micros: int = 0
    margin_micros: int = 0
    margin_pct: Optional[Decimal] = None
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_cached_input_tokens: int = 0
    token_allowance: Optional[int] = None
    over_token_allowance: bool = False
    disallowed_models: List[str] = Field(default_factory=list)
    unrated_meters: int = 0
    generated_at: datetime


@dataclass
class _Totals:
    """Per-meter accumulator used by build_statement."""

    quantity: Decimal = Decimal(0)
    cost: int = 0
    rated: bool = True


def build_statement(
    *,
    tenant_id: UUID,
    period: str,
    rated: Sequence[RatedUsage],
    plan: Optional[Plan],
    subscription: Optional[TenantSubscription],
    now: datetime,
) -> BillingStatement:
    """Compute a tenant's statement for a month from its rated usage.

    Args:
        tenant_id (UUID): Tenant id.
        period (str): "YYYY-MM".
        rated (Sequence[RatedUsage]): The month's daily usage, rated.
        plan (Optional[Plan]): Subscribed plan (None: nothing is charged,
            costs are still reported).
        subscription (Optional[TenantSubscription]): The subscription.
        now (datetime): Generation time.

    Returns:
        BillingStatement: A "preview" statement.
    """
    meters: Dict[tuple, _Totals] = {}
    messages: Dict[str, int] = {}
    channel_cost: Dict[str, int] = {}
    tokens = {UNIT_INPUT_TOKEN: 0, UNIT_OUTPUT_TOKEN: 0, UNIT_CACHED_INPUT_TOKEN: 0}
    models: set = set()

    for item in rated:
        u = item.usage
        key = (u.kind, u.provider, u.sku, u.unit, u.channel_type)
        totals = meters.setdefault(key, _Totals())
        totals.quantity += u.quantity
        totals.cost += item.cost_micros
        totals.rated = totals.rated and not item.missing_rate
        if u.channel_type:
            channel_cost[u.channel_type] = channel_cost.get(u.channel_type, 0) + item.cost_micros
        if u.kind == "platform" and u.sku == SKU_AI_MESSAGE:
            messages[u.channel_type] = messages.get(u.channel_type, 0) + int(u.quantity)
        if u.kind == "llm":
            models.add(u.sku)
            if u.unit in tokens:
                tokens[u.unit] += int(u.quantity)

    channels = sorted(set(messages) | (set(plan.included_messages) - {WILDCARD} if plan else set()))
    lines: List[StatementChannelLine] = []
    for channel in channels:
        used = messages.get(channel, 0)
        included = plan.included_for(channel) if plan else 0
        over = max(0, used - included) if plan else 0
        price = plan.overage_price_for(channel) if plan else None
        lines.append(
            StatementChannelLine(
                channel_type=channel,
                messages=used,
                included=included,
                overage_messages=over,
                overage_price_micros=price,
                overage_amount_micros=over * (price or 0),
                cost_micros=channel_cost.get(channel, 0),
            )
        )

    fee = plan.monthly_fee_micros if plan else 0
    overage = sum(line.overage_amount_micros for line in lines)
    revenue = fee + overage
    cost = sum(t.cost for t in meters.values())
    margin = revenue - cost
    allowance = plan.monthly_token_allowance if plan else None
    return BillingStatement(
        tenant_id=tenant_id,
        period=period,
        currency=plan.currency if plan else "EUR",
        plan_id=plan.id if plan else None,
        plan_code=plan.code if plan else None,
        plan_name=plan.name if plan else None,
        overage_mode=subscription.effective_mode(plan) if plan and subscription else None,
        monthly_fee_micros=fee,
        channels=lines,
        costs=[
            StatementCostLine(
                kind=k[0], provider=k[1], sku=k[2], unit=k[3], channel_type=k[4],
                quantity=t.quantity, cost_micros=t.cost, rated=t.rated,
            )
            for k, t in sorted(meters.items())
        ],
        overage_amount_micros=overage,
        revenue_micros=revenue,
        cost_micros=cost,
        margin_micros=margin,
        margin_pct=_pct(margin, revenue),
        llm_input_tokens=tokens[UNIT_INPUT_TOKEN],
        llm_output_tokens=tokens[UNIT_OUTPUT_TOKEN],
        llm_cached_input_tokens=tokens[UNIT_CACHED_INPUT_TOKEN],
        token_allowance=allowance,
        over_token_allowance=bool(
            allowance is not None and tokens[UNIT_INPUT_TOKEN] + tokens[UNIT_OUTPUT_TOKEN] > allowance
        ),
        disallowed_models=sorted(m for m in models if plan and not plan.allows_model(m)),
        unrated_meters=sum(1 for t in meters.values() if not t.rated),
        generated_at=now,
    )


def _pct(part: int, whole: int) -> Optional[Decimal]:
    """`part` as a percentage of `whole`, 1 decimal.

    Args:
        part (int): Numerator.
        whole (int): Denominator.

    Returns:
        Optional[Decimal]: The percentage, or None if `whole` is 0.
    """
    if not whole:
        return None
    return (Decimal(part) * 100 / Decimal(whole)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ChannelPricingInsight:
    """What one AI-handled message on a channel costs, and the price
    that would give the plan's margin.

    Attributes:
        channel_type (str): Channel type.
        messages (int): Messages in the sample.
        avg_cost_micros (Optional[int]): Average cost per message
            (channel + LLM), None without messages.
        suggested_price_micros (Optional[int]): avg cost x (1 + margin).
        configured_price_micros (Optional[int]): The plan's overage price.
        margin_at_configured_pct (Optional[Decimal]): Margin the configured
            price gives over the average cost.
    """

    channel_type: str
    messages: int
    avg_cost_micros: Optional[int]
    suggested_price_micros: Optional[int]
    configured_price_micros: Optional[int]
    margin_at_configured_pct: Optional[Decimal]


def pricing_insight(
    plan: Plan, rated: Sequence[RatedUsage], *, extra_channels: Sequence[str] = ()
) -> List[ChannelPricingInsight]:
    """Average cost per AI-handled message per channel over a sample of
    rated usage, and the overage price the plan's margin suggests.

    Args:
        plan (Plan): The plan.
        rated (Sequence[RatedUsage]): Sample usage (e.g. last 30 days).
        extra_channels (Sequence[str]): Channels to list even without usage.

    Returns:
        List[ChannelPricingInsight]: One entry per channel.
    """
    messages: Dict[str, int] = {}
    cost: Dict[str, int] = {}
    for item in rated:
        u = item.usage
        if not u.channel_type:
            continue
        cost[u.channel_type] = cost.get(u.channel_type, 0) + item.cost_micros
        if u.kind == "platform" and u.sku == SKU_AI_MESSAGE:
            messages[u.channel_type] = messages.get(u.channel_type, 0) + int(u.quantity)

    channels = sorted(
        set(messages) | set(extra_channels) | (set(plan.included_messages) | set(plan.overage_price_micros)) - {WILDCARD}
    )
    factor = 1 + Decimal(plan.margin_pct) / 100
    result: List[ChannelPricingInsight] = []
    for channel in channels:
        count = messages.get(channel, 0)
        avg = round(cost.get(channel, 0) / count) if count else None
        configured = plan.overage_price_for(channel)
        result.append(
            ChannelPricingInsight(
                channel_type=channel,
                messages=count,
                avg_cost_micros=avg,
                suggested_price_micros=int((Decimal(avg) * factor).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                if avg is not None
                else None,
                configured_price_micros=configured,
                margin_at_configured_pct=_pct(configured - avg, avg) if configured is not None and avg else None,
            )
        )
    return result


def previous_period(today: date) -> str:
    """The period before the month `today` is in (the one to close).

    Args:
        today (date): Today (UTC).

    Returns:
        str: "YYYY-MM" of the previous month.
    """
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{year:04d}-{month:02d}"
