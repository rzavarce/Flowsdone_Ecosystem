/** Types for the gateway's admin API (`/internal/admin/*`) as used by the console. */

import type { ProfileFields, Role, SocialNetwork } from '@/core/auth/types'

/** Channels supported by the gateway. */
export type ChannelType =
  | 'facebook'
  | 'instagram'
  | 'twitter'
  | 'whatsapp_evolution'
  | 'telegram'
  | 'tiktok'
  | 'voice'

/** Providers with one app shared across the whole platform. */
export type ChannelAppProvider = 'meta' | 'twitter' | 'tiktok' | 'twilio'

/** Lifecycle status of tenants and projects. `suspended` cuts off routing for their channels without deleting data. */
export type LifecycleStatus = 'active' | 'suspended'

/** A tenant as returned by the admin API (the session's, in `core/auth`, only carries id and name). */
export interface TenantRecord {
  id: string
  name: string
  slug: string
  status: string
  created_at: string
  updated_at: string
}

/** Input for creating a tenant. Always provisions its `client` account alongside it. */
export interface CreateTenantInput {
  name: string
  slug: string
  /** Email of the `client` account created alongside the tenant (pending, activated by email). */
  client_email: string
  /** Display name for that `client` account. */
  client_name: string
}

/** Editable fields of a tenant; omitted ones stay unchanged. */
export interface UpdateTenantInput {
  name?: string
  slug?: string
  status?: LifecycleStatus
}

/** A tenant's billing data (1:1) - pure data capture, with no billing engine
 * behind it. Everything is optional: it gets filled in gradually. */
export interface TenantBillingProfile {
  id: string
  tenant_id: string
  legal_name: string | null
  tax_id: string | null
  billing_email: string | null
  billing_contact_name: string | null
  billing_phone: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state_province: string | null
  postal_code: string | null
  country: string | null
  currency: string | null
  plan: string | null
  billing_cycle: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** Editable fields of the billing profile; omitted ones stay unchanged. */
export type UpdateTenantBillingInput = Partial<
  Omit<TenantBillingProfile, 'id' | 'tenant_id' | 'created_at' | 'updated_at'>
>

/** Editable fields of a project; omitted ones stay unchanged. */
export interface UpdateProjectInput {
  name?: string
  slug?: string
  status?: LifecycleStatus
}

/** A project as returned by the admin API; belongs to a single tenant. */
export interface Project {
  id: string
  tenant_id: string
  name: string
  slug: string
  status: string
}

/** An agent as returned by the admin API; wraps a Langflow flow within a project. */
export interface Agent {
  id: string
  project_id: string
  name: string
  langflow_flow_id: string
  is_default: boolean
  status: string
}

/** A client's connected channel. Credentials never come back in plaintext. */
export interface ChannelConnection {
  id: string
  project_id: string
  agent_id: string
  channel_type: ChannelType
  external_id: string
  display_name: string | null
  has_credentials: boolean
  config: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

/** A provider's shared credentials; only whether they're configured is known here. */
export interface ChannelApp {
  id: string
  provider: ChannelAppProvider
  has_credentials: boolean
  config: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

/** Input for creating a project under a tenant. */
export interface CreateProjectInput {
  tenant_id: string
  name: string
  slug: string
}

/** Input for creating a channel connection under a project and agent. */
export interface CreateChannelConnectionInput {
  project_id: string
  agent_id: string
  channel_type: ChannelType
  external_id: string
  display_name?: string | null
  credentials?: Record<string, string>
}

/** Editable fields of a connection; omitted ones stay unchanged. */
export interface UpdateChannelConnectionInput {
  agent_id?: string
  display_name?: string | null
  /** When sent, REPLACES the current credentials. */
  credentials?: Record<string, string>
  status?: string
}

/** Status of a console account. `pending`: created, waiting for the user to
 * activate it via the link sent by email - can't log in yet. */
export type UserAccountStatus = 'pending' | 'active' | 'disabled'

/** A console user as returned by the admin API. Never carries the password hash. */
export interface UserRecord extends ProfileFields {
  id: string
  email: string
  name: string
  role: Role
  status: UserAccountStatus
  tenant_ids: string[]
  last_login_at: string | null
  created_at: string
  updated_at: string
}

/** Input for creating a user. No password: created `pending` and activated by
 * email (see `ProvisionUserUseCase` on the backend). */
export interface CreateUserInput {
  email: string
  name: string
  role: Role
  tenant_ids: string[]
  phone?: string
  address?: string
  social_links?: Partial<Record<SocialNetwork, string>>
}

/** Editable fields of a user; omitted ones stay unchanged. */
export interface UpdateUserInput {
  name?: string
  role?: Role
  status?: 'active' | 'disabled'
  tenant_ids?: string[]
  /** An empty string clears it. */
  phone?: string
  /** An empty string clears it. */
  address?: string
  /** Replaces all the links. */
  social_links?: Partial<Record<SocialNetwork, string>>
}

/** A session for opening Langflow as a tenant's user. */
export interface LangflowSession {
  /**
   * Gateway URL loaded into the iframe. Carries a single-use ticket that
   * expires within seconds: a new one must be requested every time the
   * editor is mounted. Empty in the mock adapter (no real Langflow).
   */
  url: string
}

// ---------------------------------------------------------------- conversations

/** A conversation: one bounded exchange with a contact (closes after 24 h without messages from them or 7 days in total). */
export interface Conversation {
  id: string
  tenant_id: string
  project_id: string
  agent_id: string
  channel_type: ChannelType
  channel_connection_id: string
  contact: string
  status: 'open' | 'closed'
  started_at: string
  last_inbound_at: string
  last_message_at: string
  inbound_count: number
  outbound_count: number
  closed_at: string | null
  close_reason: 'inactivity' | 'max_duration' | 'manual' | null
}

/** Filters for listing conversations. `before` paginates (last_message_at of the previous page's last item). */
export interface ConversationFilters {
  tenant_id?: string
  project_id?: string
  channel_type?: string
  status?: 'open' | 'closed'
  contact?: string
  before?: string
  limit?: number
}

/** One message of a conversation's transcript. */
export interface ConversationMessage {
  message_id: string
  timestamp: string
  direction: 'inbound' | 'outbound'
  sender_type: 'contact' | 'bot' | 'human'
  app: string
  text: string
  /** `false` for inbound messages refused by the plan's quota (never reached the agent). */
  billable: boolean
}

/**
 * One usage meter (channel messages, LLM tokens of a model, platform messages).
 * Quantities are decimals serialized as strings; `cost_micros` is only sent to admins.
 */
export interface UsageLine {
  kind: 'channel' | 'llm' | 'platform'
  provider: string
  sku: string
  unit: string
  channel_type: string
  quantity: string
  cost_micros: number | null
  /** `false`: external usage with no rate in the cost catalog (counts as 0). */
  rated: boolean
}

/** A conversation with its transcript, usage and (admins only) cost. */
export interface ConversationDetail {
  conversation: Conversation
  messages: ConversationMessage[]
  usage: UsageLine[]
  cost_micros: number | null
  llm_input_tokens: number
  llm_output_tokens: number
  llm_cached_input_tokens: number
}

// ---------------------------------------------------------------------- billing

/** What happens once a tenant uses up the messages included in its plan. */
export type OverageMode = 'notify' | 'overage' | 'hard_stop'

/** A commercial plan. Money in micro-units (1 EUR = 1 000 000); `margin_pct` is a decimal string. */
export interface Plan {
  id: string
  code: string
  name: string
  description: string | null
  monthly_fee_micros: number
  currency: string
  /** Messages handled by the agent included per month, per channel; `*` = any other channel. */
  included_messages: Record<string, number>
  /** Price of each message beyond the included ones, per channel; `*` = any other channel. */
  overage_price_micros: Record<string, number>
  margin_pct: string
  allowed_models: string[]
  monthly_token_allowance: number | null
  default_overage_mode: OverageMode
  active: boolean
  /** Tenants subscribed to it. */
  subscriptions: number
  created_at: string | null
  updated_at: string | null
}

/** Editable fields of a plan (create requires code and name). */
export interface PlanInput {
  code?: string
  name?: string
  description?: string | null
  monthly_fee_micros?: number
  included_messages?: Record<string, number>
  overage_price_micros?: Record<string, number>
  margin_pct?: string
  allowed_models?: string[]
  monthly_token_allowance?: number | null
  default_overage_mode?: OverageMode
  active?: boolean
}

/** Average cost per agent-handled message on a channel and the overage price the plan's margin suggests. */
export interface ChannelPricing {
  channel_type: string
  messages: number
  avg_cost_micros: number | null
  suggested_price_micros: number | null
  configured_price_micros: number | null
  margin_at_configured_pct: string | null
}

/** Pricing insight of a plan over the last `days`; `sample` says whose usage it is based on. */
export interface PricingInsight {
  plan_id: string
  margin_pct: string
  days: number
  sample: 'plan' | 'platform'
  channels: ChannelPricing[]
}

/** What Flowsdone pays for a meter, from `valid_from` on (a price change is a new rate). */
export interface CostRate {
  id: string
  kind: 'channel' | 'llm' | 'platform'
  provider: string
  sku: string
  unit: string
  price_micros: number
  per_quantity: number
  currency: string
  valid_from: string
  note: string | null
  created_at: string | null
}

/** Input for a new rate; `valid_from` defaults to now. */
export interface CostRateInput {
  kind: CostRate['kind']
  provider: string
  sku: string
  unit: string
  price_micros: number
  per_quantity: number
  valid_from?: string
  note?: string | null
}

/** A meter used recently that no rate covers. */
export interface UnratedMeter {
  kind: string
  provider: string
  sku: string
  unit: string
  quantity: string
}

/** A tenant's subscription. */
export interface Subscription {
  tenant_id: string
  plan_id: string
  plan_code: string
  plan_name: string
  overage_mode: OverageMode | null
  effective_overage_mode: OverageMode
  spending_cap_micros: number | null
  started_at: string
  updated_at: string | null
}

/** Input for assigning/changing a tenant's plan. */
export interface SubscriptionInput {
  plan_id: string
  overage_mode?: OverageMode | null
  spending_cap_micros?: number | null
}

/** A statement line for one channel; `cost_micros` only for admins. */
export interface StatementChannel {
  channel_type: string
  messages: number
  included: number
  overage_messages: number
  overage_price_micros: number | null
  overage_amount_micros: number
  cost_micros: number | null
}

/** A tenant's month: `preview` (live) or `closed` (frozen). Cost/margin fields are `null` for non-admins. */
export interface Statement {
  tenant_id: string
  period: string
  status: 'preview' | 'closed'
  currency: string
  plan_id: string | null
  plan_code: string | null
  plan_name: string | null
  overage_mode: OverageMode | null
  monthly_fee_micros: number
  channels: StatementChannel[]
  costs: UsageLine[] | null
  overage_amount_micros: number
  revenue_micros: number
  cost_micros: number | null
  margin_micros: number | null
  margin_pct: string | null
  llm_input_tokens: number
  llm_output_tokens: number
  llm_cached_input_tokens: number
  token_allowance: number | null
  over_token_allowance: boolean
  disallowed_models: string[]
  unrated_meters: number | null
  generated_at: string
}
