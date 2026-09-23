import type {
  Agent,
  ChannelApp,
  ChannelAppProvider,
  ChannelConnection,
  CreateAgentInput,
  CreateChannelConnectionInput,
  LangflowFlow,
  UpdateAgentInput,
  CreateProjectInput,
  CreateTenantInput,
  CreateUserInput,
  Project,
  TenantBillingProfile,
  TenantRecord,
  UpdateChannelConnectionInput,
  UpdateProjectInput,
  UpdateTenantBillingInput,
  UpdateTenantInput,
  UpdateUserInput,
  UserRecord,
  LangflowSession,
  Conversation,
  ConversationDetail,
  ConversationFilters,
  CostRate,
  CostRateInput,
  Plan,
  PlanInput,
  PricingInsight,
  Statement,
  Subscription,
  SubscriptionInput,
  UnratedMeter,
} from './types'

/**
 * Port for the admin API. The UI only knows this interface; there is an HTTP
 * adapter (the real gateway) and a mock one (development/demos).
 *
 * Everything it returns is already filtered by what the profile is allowed to
 * see: the gateway enforces role and tenant scope (anything outside it gets a 404).
 */
export interface AdminApi {
  /** Visible tenants (all of them for an admin; only their own for anyone else). */
  listTenants(): Promise<TenantRecord[]>
  /** Admin only. */
  createTenant(input: CreateTenantInput): Promise<TenantRecord>
  /** Admin only. `status: 'suspended'` cuts off routing for all of its channels. */
  updateTenant(id: string, patch: UpdateTenantInput): Promise<TenantRecord>
  /** Admin only. Cascade-deletes its projects, agents and channels. */
  deleteTenant(id: string): Promise<void>

  /**
   * The tenant's billing profile (admin/tenant_manager). Returns an empty one
   * (all fields `null`) if nothing was ever saved - never a 404.
   */
  getTenantBilling(tenantId: string): Promise<TenantBillingProfile>
  updateTenantBilling(tenantId: string, patch: UpdateTenantBillingInput): Promise<TenantBillingProfile>

  /** Visible projects, optionally scoped to a tenant. */
  listProjects(tenantId?: string): Promise<Project[]>
  createProject(input: CreateProjectInput): Promise<Project>
  updateProject(id: string, patch: UpdateProjectInput): Promise<Project>
  /** Cascade-deletes its agents and channels. */
  deleteProject(id: string): Promise<void>

  /** Visible agents, optionally scoped to a project. */
  listAgents(projectId?: string): Promise<Agent[]>
  /**
   * Registers a flow of the project's Langflow folder as an agent. Fails with
   * 400 if the flow is not in that folder, 409 if the name is taken.
   */
  createAgent(input: CreateAgentInput): Promise<Agent>
  updateAgent(id: string, patch: UpdateAgentInput): Promise<Agent>
  /** Fails with 409 while channels are still connected to it. */
  deleteAgent(id: string): Promise<void>
  /** Flows in a project's Langflow folder (provisions the tenant's Langflow if needed). */
  listLangflowFlows(projectId: string): Promise<LangflowFlow[]>

  /** Visible channel connections, optionally scoped to a project. */
  listChannelConnections(projectId?: string): Promise<ChannelConnection[]>
  createChannelConnection(input: CreateChannelConnectionInput): Promise<ChannelConnection>
  updateChannelConnection(id: string, patch: UpdateChannelConnectionInput): Promise<ChannelConnection>
  deleteChannelConnection(id: string): Promise<void>

  /** Providers' shared apps (admin only). */
  listChannelApps(): Promise<ChannelApp[]>
  /** Creates or REPLACES a provider's credentials (admin only). */
  upsertChannelApp(provider: ChannelAppProvider, credentials: Record<string, string>): Promise<ChannelApp>
  deleteChannelApp(provider: ChannelAppProvider): Promise<void>
  /** Reveals a provider's credentials in plaintext (admin only). Use with care. */
  revealChannelAppCredentials(provider: ChannelAppProvider): Promise<Record<string, unknown>>

  /**
   * Admin only. Provisions the tenant's Langflow (its user and one folder per
   * project) and returns the single-sign-on URL for the iframe. With
   * `projectId` it opens that project's folder; without it, the first one's.
   */
  createLangflowSession(tenantId: string, projectId?: string): Promise<LangflowSession>

  /**
   * Console users (admin only). Includes each tenant's `client` account - the
   * Users screen filters them out, since they're managed from Tenants.
   */
  listUsers(): Promise<UserRecord[]>
  /** No password: stays `pending` and gets sent the activation email. */
  createUser(input: CreateUserInput): Promise<UserRecord>
  updateUser(id: string, patch: UpdateUserInput): Promise<UserRecord>
  /** Closes all of the user's active sessions. */
  deleteUser(id: string): Promise<void>
  /** Resends the activation email (only while still `pending`). */
  resendUserActivation(id: string): Promise<void>
  /** Sets (or replaces) a user's photo (admin only). */
  uploadUserAvatar(id: string, image: Blob): Promise<UserRecord>
  /** Removes a user's photo (admin only). */
  removeUserAvatar(id: string): Promise<UserRecord>
  /** URL to display a user's photo, or `null` if they have none. */
  userAvatarUrl(user: UserRecord): string | null

  /** Conversations of the visible tenants, most recent activity first (staff). */
  listConversations(filters?: ConversationFilters): Promise<Conversation[]>
  /** A conversation with its transcript and usage; cost only for admins. */
  getConversation(id: string): Promise<ConversationDetail>

  /** Commercial plans (admin only). */
  listPlans(): Promise<Plan[]>
  createPlan(input: PlanInput & { code: string; name: string }): Promise<Plan>
  updatePlan(id: string, patch: PlanInput): Promise<Plan>
  /** Fails with 409 while a tenant is subscribed (deactivate it instead). */
  deletePlan(id: string): Promise<void>
  /** Average cost per message per channel and the suggested overage price (admin only). */
  getPlanPricingInsight(id: string, days?: number): Promise<PricingInsight>

  /** The cost catalog, every version (admin only). */
  listCostRates(): Promise<CostRate[]>
  createCostRate(input: CostRateInput): Promise<CostRate>
  deleteCostRate(id: string): Promise<void>
  /** Meters used recently with no rate (admin only). */
  listUnratedMeters(days?: number): Promise<UnratedMeter[]>

  /** A tenant's subscription, or `null` if it has none (admin/tenant_manager). */
  getSubscription(tenantId: string): Promise<Subscription | null>
  /** Admin only. */
  putSubscription(tenantId: string, input: SubscriptionInput): Promise<Subscription>
  /** Admin only. */
  deleteSubscription(tenantId: string): Promise<void>
  /** A tenant's month (current if `period` is omitted): frozen if closed, live otherwise. */
  getStatement(tenantId: string, period?: string): Promise<Statement>
  /** A tenant's closed months, newest first. */
  listStatements(tenantId: string): Promise<Statement[]>
}
