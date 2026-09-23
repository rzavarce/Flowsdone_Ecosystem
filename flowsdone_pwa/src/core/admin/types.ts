/** Types for the gateway's admin API (`/internal/admin/*`) as used by the console. */

import type { Role } from '@/core/auth/types'

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
export interface UserRecord {
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
}

/** Editable fields of a user; omitted ones stay unchanged. */
export interface UpdateUserInput {
  name?: string
  role?: Role
  status?: 'active' | 'disabled'
  tenant_ids?: string[]
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
