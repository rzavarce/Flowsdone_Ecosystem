import { ApiError } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import type { Agent, ChannelApp, ChannelAppProvider, ChannelConnection, Project, TenantRecord } from './types'

/**
 * Adaptador de MAQUETA: datos en memoria coherentes con los tenants del
 * adaptador mock de autenticación, sin backend. Replica las reglas del
 * gateway que la UI necesita ver (duplicados, agente del mismo proyecto, token
 * de verificación de Meta autogenerado). No aplica alcance por tenant: la UI
 * ya filtra por el tenant activo.
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

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/** Opciones de {@link createMockAdminApi}. */
export interface MockAdminOptions {
  /** Latencia simulada por llamada, en ms. */
  latencyMs?: number
  /** Datos de partida propios (los tests los alinean con sus tenants); por defecto, los de demostración. */
  seed?: { tenants?: TenantRecord[]; projects?: Project[]; agents?: Agent[]; connections?: ChannelConnection[] }
}

/** Crea el adaptador mock; cada instancia parte de datos limpios. */
export function createMockAdminApi({ latencyMs = 250, seed = {} }: MockAdminOptions = {}): AdminApi {
  const tenants = (seed.tenants ?? TENANTS).map((t) => ({ ...t }))
  const projects = (seed.projects ?? PROJECTS).map((p) => ({ ...p }))
  const agents = (seed.agents ?? AGENTS).map((a) => ({ ...a }))
  const connections = (seed.connections ?? CONNECTIONS).map((c) => ({ ...c }))
  const apps = new Map<ChannelAppProvider, { app: ChannelApp; credentials: Record<string, unknown> }>()
  let seq = 100

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
  /** Como ON DELETE CASCADE de la base: un proyecto arrastra sus agentes y canales. */
  const cascadeProject = (projectId: string) => {
    removeWhere(connections, (c) => c.project_id !== projectId)
    removeWhere(agents, (a) => a.project_id !== projectId)
    removeWhere(projects, (p) => p.id !== projectId)
  }

  return {
    async listTenants() {
      await wait(latencyMs)
      return clone(tenants)
    },
    async createTenant(input) {
      await wait(latencyMs)
      if (tenants.some((t) => t.slug === input.slug)) throw new ApiError(409, 'already exists')
      const now = new Date().toISOString()
      const tenant: TenantRecord = { id: `t-${++seq}`, status: 'active', created_at: now, updated_at: now, ...input }
      tenants.push(tenant)
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
  }
}
