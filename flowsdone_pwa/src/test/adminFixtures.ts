import type { Agent, ChannelConnection, Project, TenantRecord, UserRecord } from '@/core/admin/types'

/**
 * Admin API data aligned with `renderApp`'s tenants (t1 Clínica Vital,
 * t2 Inmobiliaria Norte, t3 Tienda Aurora). Tenant t3 has no projects on
 * purpose: it lets tests exercise creating a project inline.
 */
const t0 = '2026-08-01T10:00:00Z'
/** The three tenants from `renderApp` with their full records; t3 (no projects) is suspended. */
export const TENANTS: TenantRecord[] = [
  { id: 't1', name: 'Clínica Vital', slug: 'clinica-vital', status: 'active', created_at: t0, updated_at: t0 },
  { id: 't2', name: 'Inmobiliaria Norte', slug: 'inmobiliaria-norte', status: 'active', created_at: t0, updated_at: t0 },
  { id: 't3', name: 'Tienda Aurora', slug: 'tienda-aurora', status: 'suspended', created_at: t0, updated_at: t0 },
]

/** Projects fixture: one for tenant t1, one for t2; t3 stays projectless on purpose. */
export const PROJECTS: Project[] = [
  { id: 'p1', tenant_id: 't1', name: 'Atención', slug: 'atencion', status: 'active' },
  { id: 'p2', tenant_id: 't2', name: 'Ventas', slug: 'ventas', status: 'active' },
]

/** Agents fixture, two under project p1 (one default) and one under p2. */
export const AGENTS: Agent[] = [
  { id: 'a1', project_id: 'p1', name: 'Recepción', langflow_flow_id: 'f1', is_default: true, status: 'active' },
  { id: 'a1b', project_id: 'p1', name: 'Citas', langflow_flow_id: 'f1b', is_default: false, status: 'active' },
  { id: 'a2', project_id: 'p2', name: 'Asesor', langflow_flow_id: 'f2', is_default: true, status: 'active' },
]

const now = '2026-09-01T10:00:00Z'
/** Builds a `ChannelConnection` fixture, filling in sensible defaults over the given overrides. */
const conn = (o: Partial<ChannelConnection> & Pick<ChannelConnection, 'id' | 'project_id' | 'agent_id' | 'channel_type' | 'external_id'>): ChannelConnection => ({
  display_name: null,
  has_credentials: false,
  config: {},
  status: 'active',
  created_at: now,
  updated_at: now,
  ...o,
})

/** Channel connections fixture spanning WhatsApp, Telegram and Instagram, with mixed credential/status states. */
export const CONNECTIONS: ChannelConnection[] = [
  conn({ id: 'c1', project_id: 'p1', agent_id: 'a1', channel_type: 'whatsapp_evolution', external_id: 'vital-wa', display_name: 'WhatsApp Clínica' }),
  conn({ id: 'c2', project_id: 'p1', agent_id: 'a1b', channel_type: 'telegram', external_id: '123456789:SECRETTOKEN', display_name: 'Bot de citas', has_credentials: true }),
  conn({ id: 'c3', project_id: 'p2', agent_id: 'a2', channel_type: 'instagram', external_id: '17841400000000', display_name: 'Instagram Norte', has_credentials: true, status: 'inactive' }),
]

/** Users fixture covering each role (admin, tenant_manager, botmaster, client) with varied statuses. */
export const USERS: UserRecord[] = [
  { id: 'u1', email: 'ana@flowsdone.com', name: 'Ana Admin', role: 'admin', status: 'active', tenant_ids: [], last_login_at: now, created_at: t0, updated_at: t0 },
  { id: 'u2', email: 'marcos@flowsdone.com', name: 'Marcos Gestor', role: 'tenant_manager', status: 'active', tenant_ids: ['t1'], last_login_at: now, created_at: t0, updated_at: t0 },
  { id: 'u3', email: 'bea@flowsdone.com', name: 'Bea Botmaster', role: 'botmaster', status: 'pending', tenant_ids: ['t1', 't2'], last_login_at: null, created_at: t0, updated_at: t0 },
  { id: 'u4', email: 'carla@clinica-vital.com', name: 'Carla Cliente', role: 'client', status: 'active', tenant_ids: ['t1'], last_login_at: now, created_at: t0, updated_at: t0 },
]

/** Full fixture set, ready to seed the mock admin API. */
export const SEED = { tenants: TENANTS, projects: PROJECTS, agents: AGENTS, connections: CONNECTIONS, users: USERS }
