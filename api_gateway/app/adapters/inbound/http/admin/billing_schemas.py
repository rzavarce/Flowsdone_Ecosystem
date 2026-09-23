"""Pydantic request/response schemas for the conversations and billing
admin API. Money is always integer micro-units (1 EUR = 1_000_000);
percentages and quantities are decimals serialized as strings.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.billing import OverageMode
from app.domain.models.usage import UsageKind


# Conversations

class ConversationOut(BaseModel):
    """A conversation record.

    Attributes:
        id (UUID): Conversation id.
        tenant_id (UUID): Tenant id.
        project_id (UUID): Project id.
        agent_id (UUID): Agent id.
        channel_type (str): Channel.
        channel_connection_id (UUID): Channel connection id.
        contact (str): Contact (phone number, username...).
        status (str): "open" or "closed".
        started_at (datetime): Start.
        last_inbound_at (datetime): Contact's last message.
        last_message_at (datetime): Last message either way.
        inbound_count (int): Messages from the contact.
        outbound_count (int): Messages to the contact.
        closed_at (Optional[datetime]): End.
        close_reason (Optional[str]): Why it ended.
    """

    id: UUID
    tenant_id: UUID
    project_id: UUID
    agent_id: UUID
    channel_type: str
    channel_connection_id: UUID
    contact: str
    status: str
    started_at: datetime
    last_inbound_at: datetime
    last_message_at: datetime
    inbound_count: int
    outbound_count: int
    closed_at: Optional[datetime] = None
    close_reason: Optional[str] = None


class ConversationMessageOut(BaseModel):
    """One message of a transcript.

    Attributes:
        message_id (UUID): Message id.
        timestamp (datetime): When.
        direction (str): "inbound" or "outbound".
        sender_type (str): "contact", "bot" or "human".
        app (str): App handling the conversation.
        text (str): Text.
        billable (bool): False for inbound messages refused by the quota.
    """

    message_id: UUID
    timestamp: datetime
    direction: str
    sender_type: str
    app: str
    text: str
    billable: bool = True


class UsageLineOut(BaseModel):
    """One rated usage meter.

    Attributes:
        kind (str): "channel", "llm" or "platform".
        provider (str): Provider.
        sku (str): SKU.
        unit (str): Unit.
        channel_type (str): Channel.
        quantity (Decimal): Quantity.
        cost_micros (Optional[int]): Cost (hidden for non-admins).
        rated (bool): Whether a rate applied.
    """

    kind: str
    provider: str
    sku: str
    unit: str
    channel_type: str = ""
    quantity: Decimal
    cost_micros: Optional[int] = None
    rated: bool = True


class ConversationDetailOut(BaseModel):
    """A conversation with its transcript and usage.

    Attributes:
        conversation (ConversationOut): The record.
        messages (List[ConversationMessageOut]): Transcript, oldest first.
        usage (List[UsageLineOut]): Usage per meter (summed over days).
        cost_micros (Optional[int]): Total cost (admin only).
        llm_input_tokens (int): Input tokens.
        llm_output_tokens (int): Output tokens.
        llm_cached_input_tokens (int): Cached input tokens.
    """

    conversation: ConversationOut
    messages: List[ConversationMessageOut]
    usage: List[UsageLineOut]
    cost_micros: Optional[int] = None
    llm_input_tokens: int
    llm_output_tokens: int
    llm_cached_input_tokens: int


# Plans

class PlanFields(BaseModel):
    """Editable fields of a plan (shared by create and update).

    Attributes:
        code (Optional[str]): Unique short code.
        name (Optional[str]): Display name.
        description (Optional[str]): Free text.
        monthly_fee_micros (Optional[int]): Monthly fee.
        included_messages (Optional[Dict[str, int]]): Per channel ("*" = rest).
        overage_price_micros (Optional[Dict[str, int]]): Per channel ("*" = rest).
        margin_pct (Optional[Decimal]): Target margin over cost, %.
        allowed_models (Optional[List[str]]): Model patterns; empty = any.
        monthly_token_allowance (Optional[int]): Fair-use tokens/month.
        default_overage_mode (Optional[OverageMode]): Default mode.
        active (Optional[bool]): Assignable to new subscriptions.
    """

    code: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    monthly_fee_micros: Optional[int] = Field(default=None, ge=0)
    included_messages: Optional[Dict[str, int]] = None
    overage_price_micros: Optional[Dict[str, int]] = None
    margin_pct: Optional[Decimal] = Field(default=None, ge=0, le=10000)
    allowed_models: Optional[List[str]] = None
    monthly_token_allowance: Optional[int] = Field(default=None, ge=0)
    default_overage_mode: Optional[OverageMode] = None
    active: Optional[bool] = None


class PlanCreate(PlanFields):
    """Request body for POST /plans (code and name required).

    Attributes:
        code (str): Unique short code.
        name (str): Display name.
    """

    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)


class PlanOut(BaseModel):
    """A plan.

    Attributes:
        id (UUID): Plan id.
        code (str): Code.
        name (str): Name.
        description (Optional[str]): Description.
        monthly_fee_micros (int): Fee.
        currency (str): Currency.
        included_messages (Dict[str, int]): Included per channel.
        overage_price_micros (Dict[str, int]): Overage price per channel.
        margin_pct (Decimal): Target margin.
        allowed_models (List[str]): Allowed models.
        monthly_token_allowance (Optional[int]): Fair-use tokens.
        default_overage_mode (str): Default mode.
        active (bool): Active.
        subscriptions (int): Tenants on this plan.
        created_at (Optional[datetime]): Created.
        updated_at (Optional[datetime]): Updated.
    """

    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    monthly_fee_micros: int
    currency: str
    included_messages: Dict[str, int]
    overage_price_micros: Dict[str, int]
    margin_pct: Decimal
    allowed_models: List[str]
    monthly_token_allowance: Optional[int] = None
    default_overage_mode: str
    active: bool
    subscriptions: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ChannelPricingOut(BaseModel):
    """Pricing insight for one channel.

    Attributes:
        channel_type (str): Channel.
        messages (int): Messages in the sample.
        avg_cost_micros (Optional[int]): Average cost per message.
        suggested_price_micros (Optional[int]): avg x (1 + margin).
        configured_price_micros (Optional[int]): Current overage price.
        margin_at_configured_pct (Optional[Decimal]): Margin it gives.
    """

    channel_type: str
    messages: int
    avg_cost_micros: Optional[int] = None
    suggested_price_micros: Optional[int] = None
    configured_price_micros: Optional[int] = None
    margin_at_configured_pct: Optional[Decimal] = None


class PricingInsightOut(BaseModel):
    """Pricing insight of a plan.

    Attributes:
        plan_id (UUID): Plan id.
        margin_pct (Decimal): Target margin.
        days (int): Sample length.
        sample (str): "plan" or "platform".
        channels (List[ChannelPricingOut]): Per channel.
    """

    plan_id: UUID
    margin_pct: Decimal
    days: int
    sample: str
    channels: List[ChannelPricingOut]


# Cost catalog

class CostRateCreate(BaseModel):
    """Request body for POST /cost-rates.

    Attributes:
        kind (UsageKind): "channel", "llm" or "platform".
        provider (str): Provider or "*".
        sku (str): Exact SKU, "prefix*" or "*".
        unit (str): Unit.
        price_micros (int): Cost of `per_quantity` units.
        per_quantity (int): Units the price is for (1_000_000 = per million).
        valid_from (Optional[datetime]): From when; now if omitted.
        note (Optional[str]): Note.
    """

    kind: UsageKind
    provider: str = Field(min_length=1, max_length=100)
    sku: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=50)
    price_micros: int = Field(ge=0)
    per_quantity: int = Field(default=1, gt=0)
    valid_from: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=500)


class CostRateOut(CostRateCreate):
    """A cost rate.

    Attributes:
        id (UUID): Rate id.
        currency (str): Currency.
        valid_from (datetime): From when.
        created_at (Optional[datetime]): Entered.
    """

    id: UUID
    currency: str
    valid_from: datetime
    created_at: Optional[datetime] = None


class UnratedMeterOut(BaseModel):
    """A meter with usage but no rate.

    Attributes:
        kind (str): Kind.
        provider (str): Provider.
        sku (str): SKU.
        unit (str): Unit.
        quantity (Decimal): Unrated quantity.
    """

    kind: str
    provider: str
    sku: str
    unit: str
    quantity: Decimal


# Subscriptions and statements

class SubscriptionUpdate(BaseModel):
    """Request body for PUT /tenants/{id}/subscription.

    Attributes:
        plan_id (UUID): Plan to subscribe to (must be active).
        overage_mode (Optional[OverageMode]): Override; None = plan default.
        spending_cap_micros (Optional[int]): Overage cap; None = no cap.
    """

    plan_id: UUID
    overage_mode: Optional[OverageMode] = None
    spending_cap_micros: Optional[int] = Field(default=None, ge=0)


class SubscriptionOut(BaseModel):
    """A tenant's subscription.

    Attributes:
        tenant_id (UUID): Tenant id.
        plan_id (UUID): Plan id.
        plan_code (str): Plan code.
        plan_name (str): Plan name.
        overage_mode (Optional[str]): Override.
        effective_overage_mode (str): Mode in force.
        spending_cap_micros (Optional[int]): Cap.
        started_at (datetime): Start.
        updated_at (Optional[datetime]): Last change.
    """

    tenant_id: UUID
    plan_id: UUID
    plan_code: str
    plan_name: str
    overage_mode: Optional[str] = None
    effective_overage_mode: str
    spending_cap_micros: Optional[int] = None
    started_at: datetime
    updated_at: Optional[datetime] = None


class StatementChannelOut(BaseModel):
    """A statement's line for one channel.

    Attributes:
        channel_type (str): Channel.
        messages (int): AI-handled messages.
        included (int): Included.
        overage_messages (int): Beyond included.
        overage_price_micros (Optional[int]): Price per overage message.
        overage_amount_micros (int): Overage charged.
        cost_micros (Optional[int]): Cost (admin only).
    """

    channel_type: str
    messages: int
    included: int
    overage_messages: int
    overage_price_micros: Optional[int] = None
    overage_amount_micros: int
    cost_micros: Optional[int] = None


class StatementOut(BaseModel):
    """A monthly statement. Cost/margin fields are null for non-admins.

    Attributes:
        tenant_id (UUID): Tenant id.
        period (str): "YYYY-MM".
        status (str): "preview" or "closed".
        currency (str): Currency.
        plan_id (Optional[UUID]): Plan id.
        plan_code (Optional[str]): Plan code.
        plan_name (Optional[str]): Plan name.
        overage_mode (Optional[str]): Mode.
        monthly_fee_micros (int): Fee.
        channels (List[StatementChannelOut]): Per channel.
        costs (Optional[List[UsageLineOut]]): Per meter (admin only).
        overage_amount_micros (int): Total overage.
        revenue_micros (int): Fee + overage.
        cost_micros (Optional[int]): Total cost (admin only).
        margin_micros (Optional[int]): Margin (admin only).
        margin_pct (Optional[Decimal]): Margin % (admin only).
        llm_input_tokens (int): Input tokens.
        llm_output_tokens (int): Output tokens.
        llm_cached_input_tokens (int): Cached input tokens.
        token_allowance (Optional[int]): Fair-use tokens.
        over_token_allowance (bool): Above it.
        disallowed_models (List[str]): Models outside the plan.
        unrated_meters (Optional[int]): Meters without rate (admin only).
        generated_at (datetime): Computed at.
    """

    tenant_id: UUID
    period: str
    status: str
    currency: str
    plan_id: Optional[UUID] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    overage_mode: Optional[str] = None
    monthly_fee_micros: int
    channels: List[StatementChannelOut]
    costs: Optional[List[UsageLineOut]] = None
    overage_amount_micros: int
    revenue_micros: int
    cost_micros: Optional[int] = None
    margin_micros: Optional[int] = None
    margin_pct: Optional[Decimal] = None
    llm_input_tokens: int
    llm_output_tokens: int
    llm_cached_input_tokens: int
    token_allowance: Optional[int] = None
    over_token_allowance: bool
    disallowed_models: List[str]
    unrated_meters: Optional[int] = None
    generated_at: datetime


class ClosePeriodOut(BaseModel):
    """Result of closing a period.

    Attributes:
        period (str): "YYYY-MM".
        closed (int): Statements closed now.
    """

    period: str
    closed: int
