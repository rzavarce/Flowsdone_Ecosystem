import { ApiError } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import { createMockBilling } from './mockBilling'
import type {
  Agent,
  LangflowFlow,
  OnboardingCheck,
  ChannelApp,
  ChannelAppProvider,
  ChannelConnection,
  Project,
  TenantBillingProfile,
  TenantRecord,
  UserRecord,
} from './types'

/**
 * MOCK adapter: in-memory data consistent with the auth mock adapter's
 * tenants, with no backend. Replicates the gateway rules the UI needs to see
 * (duplicates, agent belonging to the same project, auto-generated Meta
 * verification token). Doesn't enforce tenant scope: the UI already filters
 * by the active tenant.
 */

const NOW = '2026-09-01T10:00:00Z'

const TENANTS: TenantRecord[] = [
  { id: 't-vital', name: 'Clínica Vital', slug: 'clinica-vital', status: 'active', created_at: NOW, updated_at: NOW },
  { id: 't-norte', name: 'Inmobiliaria Norte', slug: 'inmobiliaria-norte', status: 'active', created_at: NOW, updated_at: NOW },
  { id: 't-aurora', name: 'Tienda Aurora', slug: 'tienda-aurora', status: 'active', created_at: NOW, updated_at: NOW },
  { id: 't-fibra', name: 'Fibra Hogar', slug: 'fibra-hogar', status: 'suspended', created_at: NOW, updated_at: NOW },
]

const PROJECTS: Project[] = [
  { id: 'p-vital-1', tenant_id: 't-vital', name: 'Atención al paciente', slug: 'atencion', status: 'active' },
  { id: 'p-norte-1', tenant_id: 't-norte', name: 'Ventas', slug: 'ventas', status: 'active' },
  { id: 'p-aurora-1', tenant_id: 't-aurora', name: 'Soporte tienda', slug: 'soporte', status: 'active' },
]

const AGENTS: Agent[] = [
  { id: 'a-vital-1', project_id: 'p-vital-1', name: 'Recepción Vital', langflow_flow_id: 'flow-1', is_default: true, status: 'active' },
  { id: 'a-vital-2', project_id: 'p-vital-1', name: 'Citas', langflow_flow_id: 'flow-2', is_default: false, status: 'active' },
  { id: 'a-norte-1', project_id: 'p-norte-1', name: 'Asesor inmobiliario', langflow_flow_id: 'flow-3', is_default: true, status: 'active' },
  { id: 'a-aurora-1', project_id: 'p-aurora-1', name: 'Soporte Aurora', langflow_flow_id: 'flow-4', is_default: true, status: 'active' },
]

const CONNECTIONS: ChannelConnection[] = [
  { id: 'c-1', project_id: 'p-vital-1', agent_id: 'a-vital-1', channel_type: 'whatsapp_evolution', external_id: 'vital-wa', display_name: 'WhatsApp Clínica', has_credentials: false, config: {}, status: 'active', created_at: NOW, updated_at: NOW },
  { id: 'c-2', project_id: 'p-vital-1', agent_id: 'a-vital-2', channel_type: 'telegram', external_id: '123456789:AAF-mock-token', display_name: 'Bot de citas', has_credentials: true, config: {}, status: 'active', created_at: NOW, updated_at: NOW },
  { id: 'c-3', project_id: 'p-norte-1', agent_id: 'a-norte-1', channel_type: 'instagram', external_id: '17841400000000', display_name: 'Instagram Norte', has_credentials: true, config: {}, status: 'active', created_at: NOW, updated_at: NOW },
  { id: 'c-4', project_id: 'p-aurora-1', agent_id: 'a-aurora-1', channel_type: 'facebook', external_id: '102030405060', display_name: null, has_credentials: true, config: {}, status: 'inactive', created_at: NOW, updated_at: NOW },
]

const USERS: UserRecord[] = [
  { id: 'u-admin', email: 'admin@flowsdone.dev', name: 'Ana Administradora', role: 'admin', status: 'active', tenant_ids: [], last_login_at: NOW, created_at: NOW, updated_at: NOW },
  { id: 'u-manager', email: 'gestor@flowsdone.dev', name: 'Marcos Gestor', role: 'tenant_manager', status: 'active', tenant_ids: ['t-vital', 't-norte'], last_login_at: NOW, created_at: NOW, updated_at: NOW },
  { id: 'u-botmaster', email: 'botmaster@flowsdone.dev', name: 'Bea Botmaster', role: 'botmaster', status: 'pending', tenant_ids: ['t-vital', 't-norte', 't-aurora'], last_login_at: null, created_at: NOW, updated_at: NOW },
  { id: 'u-client', email: 'cliente@flowsdone.dev', name: 'Carla Cliente', role: 'client', status: 'active', tenant_ids: ['t-vital'], last_login_at: NOW, created_at: NOW, updated_at: NOW },
]

/** Simulates network latency by resolving after the given delay. */
const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/** Options for {@link createMockAdminApi}. */
export interface MockAdminOptions {
  /** Simulated latency per call, in ms. */
  latencyMs?: number
  /** Custom seed data (tests align it with their own tenants); defaults to the demo data. */
  seed?: {
    tenants?: TenantRecord[]
    projects?: Project[]
    agents?: Agent[]
    connections?: ChannelConnection[]
    users?: UserRecord[]
  }
}

/** Creates the mock adapter; each instance starts from fresh data. */
export function createMockAdminApi({ latencyMs = 250, seed = {} }: MockAdminOptions = {}): AdminApi {
  const tenants = (seed.tenants ?? TENANTS).map((t) => ({ ...t }))
  const projects = (seed.projects ?? PROJECTS).map((p) => ({ ...p }))
  const agents = (seed.agents ?? AGENTS).map((a) => ({ ...a }))
  const connections = (seed.connections ?? CONNECTIONS).map((c) => ({ ...c }))
  const users = (seed.users ?? USERS).map((u) => ({ ...u }))
  /** Photos (object URLs) by user id: the mock has no server to serve them from. */
  const avatars = new Map<string, string>()
  const apps = new Map<ChannelAppProvider, { app: ChannelApp; credentials: Record<string, unknown> }>()
  const billingProfiles = new Map<string, TenantBillingProfile>()
  let seq = 100

  const emptyBillingProfile = (tenantId: string): TenantBillingProfile => ({
    id: `bp-${tenantId}`,
    tenant_id: tenantId,
    legal_name: null,
    tax_id: null,
    billing_email: null,
    billing_contact_name: null,
    billing_phone: null,
    address_line1: null,
    address_line2: null,
    city: null,
    state_province: null,
    postal_code: null,
    country: null,
    currency: null,
    plan: null,
    billing_cycle: null,
    notes: null,
    created_at: NOW,
    updated_at: NOW,
  })

  /**
   * Flows in each project's Langflow folder: the ones its agents run, plus
   * two not registered yet (as if just imported in the editor).
   */
  const extraFlows = new Map<string, { id: string; name: string }[]>()
  const flowsOf = (projectId: string): LangflowFlow[] => {
    if (!extraFlows.has(projectId)) {
      extraFlows.set(projectId, [
        { id: `${projectId}-flow-asistente`, name: 'Asistente de ventas' },
        { id: `${projectId}-flow-faq`, name: 'Preguntas frecuentes' },
      ])
    }
    const own = agents
      .filter((a) => a.project_id === projectId)
      .map((a) => ({ id: a.langflow_flow_id, name: `Flujo de ${a.name}` }))
    const byId = new Map([...own, ...extraFlows.get(projectId)!].map((f) => [f.id, f]))
    return [...byId.values()]
      .map((f) => ({
        ...f,
        description: null,
        agent_id: agents.find((a) => a.project_id === projectId && a.langflow_flow_id === f.id)?.id ?? null,
      }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }
  /** Like the gateway: at most one default agent per project. */
  const makeOnlyDefault = (agent: Agent) => {
    for (const other of agents) if (other.project_id === agent.project_id && other.id !== agent.id) other.is_default = false
  }

  const need = <T>(item: T | undefined, what: string): T => {
    if (!item) throw new ApiError(404, `${what} not found`)
    return item
  }
  const assertAgentInProject = (agentId: string, projectId: string) => {
    if (agents.find((a) => a.id === agentId)?.project_id !== projectId) {
      throw new ApiError(400, 'agent does not belong to the project')
    }
  }
  const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T
  const removeWhere = <T,>(list: T[], keep: (item: T) => boolean) => {
    const kept = list.filter(keep)
    list.splice(0, list.length, ...kept)
  }
  /** Like ON DELETE CASCADE in the database: a project takes its agents and channels down with it. */
  const cascadeProject = (projectId: string) => {
    removeWhere(connections, (c) => c.project_id !== projectId)
    removeWhere(agents, (a) => a.project_id !== projectId)
    removeWhere(projects, (p) => p.id !== projectId)
  }

  const billing = createMockBilling({ latencyMs, tenants, projects, connections })

  return {
    // Conversaciones y facturación: módulo aparte, sobre los mismos datos vivos.
    ...billing,
    async listTenants() {
      await wait(latencyMs)
      return clone(tenants)
    },
    async createTenant({ client_email, client_name, ...input }) {
      await wait(latencyMs)
      if (tenants.some((t) => t.slug === input.slug)) throw new ApiError(409, 'already exists')
      if (users.some((u) => u.email === client_email.trim().toLowerCase())) throw new ApiError(409, 'already exists')
      const now = new Date().toISOString()
      const tenant: TenantRecord = { id: `t-${++seq}`, status: 'active', created_at: now, updated_at: now, ...input }
      tenants.push(tenant)
      // Como CreateTenantUseCase: el tenant siempre trae su usuario `client`, pending.
      users.push({
        id: `u-${++seq}`,
        email: client_email.trim().toLowerCase(),
        name: client_name,
        role: 'client',
        status: 'pending',
        tenant_ids: [tenant.id],
        last_login_at: null,
        created_at: now,
        updated_at: now,
      })
      return clone(tenant)
    },
    async updateTenant(id, patch) {
      await wait(latencyMs)
      const tenant = need(tenants.find((t) => t.id === id), 'tenant')
      if (patch.slug && tenants.some((t) => t.id !== id && t.slug === patch.slug)) throw new ApiError(409, 'already exists')
      Object.assign(tenant, patch, { updated_at: new Date().toISOString() })
      return clone(tenant)
    },
    async deleteTenant(id) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === id), 'tenant')
      for (const p of projects.filter((p) => p.tenant_id === id)) cascadeProject(p.id)
      removeWhere(tenants, (t) => t.id !== id)
      billingProfiles.delete(id)
    },

    async getTenantBilling(tenantId) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      return clone(billingProfiles.get(tenantId) ?? emptyBillingProfile(tenantId))
    },
    async updateTenantBilling(tenantId, patch) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      const current = billingProfiles.get(tenantId) ?? emptyBillingProfile(tenantId)
      const updated: TenantBillingProfile = { ...current, ...patch, updated_at: new Date().toISOString() }
      billingProfiles.set(tenantId, updated)
      return clone(updated)
    },

    async listProjects(tenantId) {
      await wait(latencyMs)
      return clone(projects.filter((p) => !tenantId || p.tenant_id === tenantId))
    },
    async createProject(input) {
      await wait(latencyMs)
      if (projects.some((p) => p.tenant_id === input.tenant_id && p.slug === input.slug)) {
        throw new ApiError(409, 'already exists')
      }
      const project: Project = { id: `p-${++seq}`, status: 'active', ...input }
      projects.push(project)
      return clone(project)
    },

    async updateProject(id, patch) {
      await wait(latencyMs)
      const project = need(projects.find((p) => p.id === id), 'project')
      if (patch.slug && projects.some((p) => p.id !== id && p.tenant_id === project.tenant_id && p.slug === patch.slug)) {
        throw new ApiError(409, 'already exists')
      }
      Object.assign(project, patch)
      return clone(project)
    },
    async deleteProject(id) {
      await wait(latencyMs)
      need(projects.find((p) => p.id === id), 'project')
      cascadeProject(id)
    },

    async listAgents(projectId) {
      await wait(latencyMs)
      return clone(agents.filter((a) => !projectId || a.project_id === projectId))
    },
    async createAgent(input) {
      await wait(latencyMs)
      need(projects.find((p) => p.id === input.project_id), 'project')
      if (!flowsOf(input.project_id).some((f) => f.id === input.langflow_flow_id)) {
        throw new ApiError(400, "flow not found in the project's Langflow folder")
      }
      if (agents.some((a) => a.project_id === input.project_id && a.name === input.name)) throw new ApiError(409, 'already exists')
      const first = !agents.some((a) => a.project_id === input.project_id)
      const agent: Agent = {
        id: `a-${++seq}`,
        project_id: input.project_id,
        name: input.name,
        langflow_flow_id: input.langflow_flow_id,
        is_default: first || Boolean(input.is_default),
        status: 'active',
      }
      agents.push(agent)
      if (agent.is_default) makeOnlyDefault(agent)
      return clone(agent)
    },
    async updateAgent(id, patch) {
      await wait(latencyMs)
      const agent = need(agents.find((a) => a.id === id), 'agent')
      if (patch.langflow_flow_id && patch.langflow_flow_id !== agent.langflow_flow_id &&
          !flowsOf(agent.project_id).some((f) => f.id === patch.langflow_flow_id)) {
        throw new ApiError(400, "flow not found in the project's Langflow folder")
      }
      if (patch.name && agents.some((a) => a.id !== id && a.project_id === agent.project_id && a.name === patch.name)) {
        throw new ApiError(409, 'already exists')
      }
      Object.assign(agent, patch)
      if (patch.is_default) makeOnlyDefault(agent)
      return clone(agent)
    },
    async deleteAgent(id) {
      await wait(latencyMs)
      need(agents.find((a) => a.id === id), 'agent')
      if (connections.some((c) => c.agent_id === id)) throw new ApiError(409, 'agent has channels')
      removeWhere(agents, (a) => a.id !== id)
    },
    async createBaseAgent(input) {
      await wait(latencyMs)
      need(projects.find((p) => p.id === input.project_id), 'project')
      // Como el gateway: crea el flujo en la carpeta y lo registra como predeterminado.
      const flowId = `${input.project_id}-flow-base-${++seq}`
      extraFlows.set(input.project_id, [...(extraFlows.get(input.project_id) ?? []), { id: flowId, name: input.assistant_name }])
      return this.createAgent({ project_id: input.project_id, name: input.assistant_name, langflow_flow_id: flowId, is_default: true })
    },
    async getOnboarding(tenantId) {
      const tenant = need(tenants.find((t) => t.id === tenantId), 'tenant')
      const profile = billingProfiles.get(tenantId)
      const subscription = await billing.getSubscription(tenantId)
      const own = projects.filter((p) => p.tenant_id === tenantId).sort((a, b) => a.name.localeCompare(b.name))
      const ownAgents = agents.filter((a) => own.some((p) => p.id === a.project_id))
      const agent = ownAgents.find((a) => a.is_default) ?? ownAgents[0]
      const client = users.find((u) => u.role === 'client' && u.tenant_ids.includes(tenantId))
      const channels = connections.filter((c) => own.some((p) => p.id === c.project_id)).length
      const checks: OnboardingCheck[] = [
        { key: 'billing', status: profile?.billing_email ? 'ok' : 'missing', detail: profile?.legal_name ?? null },
        { key: 'client_account', status: !client ? 'missing' : client.status === 'active' ? 'ok' : 'warning', detail: client?.status ?? null },
        { key: 'plan', status: subscription ? 'ok' : 'missing', detail: subscription?.plan_name ?? null },
        { key: 'project', status: own.length ? 'ok' : 'missing', detail: own[0]?.name ?? null },
        { key: 'agent', status: agent ? 'ok' : 'missing', detail: agent?.name ?? null },
        { key: 'channel', status: channels ? 'ok' : 'warning', detail: String(channels) },
      ]
      const next_step = !profile?.billing_email ? 'company' : !subscription ? 'plan' : !own.length ? 'project' : !agent ? 'agent' : 'summary'
      return clone({ tenant_id: tenant.id, next_step, project_id: own[0]?.id ?? null, checks })
    },
    async listLangflowFlows(projectId) {
      await wait(latencyMs)
      need(projects.find((p) => p.id === projectId), 'project')
      return clone(flowsOf(projectId))
    },

    async listChannelConnections(projectId) {
      await wait(latencyMs)
      return clone(connections.filter((c) => !projectId || c.project_id === projectId))
    },
    async createChannelConnection(input) {
      await wait(latencyMs)
      need(projects.find((p) => p.id === input.project_id), 'project')
      assertAgentInProject(input.agent_id, input.project_id)
      if (connections.some((c) => c.channel_type === input.channel_type && c.external_id === input.external_id)) {
        throw new ApiError(409, 'already exists')
      }
      const now = new Date().toISOString()
      const connection: ChannelConnection = {
        id: `c-${++seq}`,
        project_id: input.project_id,
        agent_id: input.agent_id,
        channel_type: input.channel_type,
        external_id: input.external_id,
        display_name: input.display_name ?? null,
        has_credentials: Object.keys(input.credentials ?? {}).length > 0,
        config: {},
        status: 'active',
        created_at: now,
        updated_at: now,
      }
      connections.push(connection)
      return clone(connection)
    },
    async updateChannelConnection(id, patch) {
      await wait(latencyMs)
      const current = need(connections.find((c) => c.id === id), 'channel_connection')
      if (patch.agent_id) assertAgentInProject(patch.agent_id, current.project_id)
      if (patch.agent_id !== undefined) current.agent_id = patch.agent_id
      if (patch.display_name !== undefined) current.display_name = patch.display_name
      if (patch.status !== undefined) current.status = patch.status
      if (patch.credentials !== undefined) current.has_credentials = Object.keys(patch.credentials).length > 0
      current.updated_at = new Date().toISOString()
      return clone(current)
    },
    async deleteChannelConnection(id) {
      await wait(latencyMs)
      const index = connections.findIndex((c) => c.id === id)
      need(index >= 0 ? connections[index] : undefined, 'channel_connection')
      connections.splice(index, 1)
    },

    async listChannelApps() {
      await wait(latencyMs)
      return clone([...apps.values()].map((entry) => entry.app))
    },
    async upsertChannelApp(provider, credentials) {
      await wait(latencyMs)
      const now = new Date().toISOString()
      const stored: Record<string, unknown> = { ...credentials }
      // Como el gateway: Meta necesita un token de verificación y, si no se da, lo genera.
      if (provider === 'meta' && !stored.webhook_verify_token) {
        stored.webhook_verify_token = apps.get('meta')?.credentials.webhook_verify_token ?? `mock-${Math.random().toString(16).slice(2, 18)}`
      }
      const app: ChannelApp = {
        id: apps.get(provider)?.app.id ?? `app-${provider}`,
        provider,
        has_credentials: Object.keys(stored).length > 0,
        config: {},
        status: 'active',
        created_at: apps.get(provider)?.app.created_at ?? now,
        updated_at: now,
      }
      apps.set(provider, { app, credentials: stored })
      return clone(app)
    },
    async deleteChannelApp(provider) {
      await wait(latencyMs)
      if (!apps.delete(provider)) throw new ApiError(404, 'channel_app not found')
    },
    async createLangflowSession(tenantId) {
      await wait(latencyMs)
      need(tenants.find((t) => t.id === tenantId), 'tenant')
      return { url: '' } // sin Langflow real: la UI muestra la maqueta del lienzo
    },
    async revealChannelAppCredentials(provider) {
      await wait(latencyMs)
      return clone(need(apps.get(provider), 'channel_app').credentials)
    },

    async listUsers() {
      await wait(latencyMs)
      return clone(users)
    },
    async createUser(input) {
      await wait(latencyMs)
      const email = input.email.trim().toLowerCase()
      if (users.some((u) => u.email === email)) throw new ApiError(409, 'already exists')
      const now = new Date().toISOString()
      const user: UserRecord = {
        id: `u-${++seq}`,
        email,
        name: input.name,
        role: input.role,
        status: 'pending',
        tenant_ids: input.role === 'admin' ? [] : input.tenant_ids,
        phone: input.phone?.trim() || null,
        address: input.address?.trim() || null,
        social_links: input.social_links ?? {},
        last_login_at: null,
        created_at: now,
        updated_at: now,
      }
      users.push(user)
      return clone(user)
    },
    async updateUser(id, patch) {
      await wait(latencyMs)
      const user = need(users.find((u) => u.id === id), 'user')
      const { phone, address, ...rest } = patch
      Object.assign(user, rest, { updated_at: new Date().toISOString() })
      // Como el gateway: una cadena vacía borra el dato.
      if (phone !== undefined) user.phone = phone.trim() || null
      if (address !== undefined) user.address = address.trim() || null
      return clone(user)
    },
    async deleteUser(id) {
      await wait(latencyMs)
      need(users.find((u) => u.id === id), 'user')
      removeWhere(users, (u) => u.id !== id)
    },
    async resendUserActivation(id) {
      await wait(latencyMs)
      const user = need(users.find((u) => u.id === id), 'user')
      if (user.status !== 'pending') throw new ApiError(404, 'user not found or not pending')
    },
    async uploadUserAvatar(id, image) {
      await wait(latencyMs)
      const user = need(users.find((u) => u.id === id), 'user')
      avatars.set(id, URL.createObjectURL(image))
      user.avatar_updated_at = new Date().toISOString()
      return clone(user)
    },
    async removeUserAvatar(id) {
      await wait(latencyMs)
      const user = need(users.find((u) => u.id === id), 'user')
      avatars.delete(id)
      user.avatar_updated_at = null
      return clone(user)
    },
    userAvatarUrl(user) {
      return avatars.get(user.id) ?? null
    },
  }
}
