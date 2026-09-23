import type {
  Agent,
  ChannelApp,
  ChannelAppProvider,
  ChannelConnection,
  CreateChannelConnectionInput,
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
}
