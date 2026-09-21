import type { Agent, ChannelConnection, Project } from '@/core/admin/types'

/**
 * Datos de la API admin alineados con los tenants de `renderApp` (t1 Clínica Vital,
 * t2 Inmobiliaria Norte, t3 Tienda Aurora). El tenant t3 no tiene proyectos, a propósito:
 * permite probar el alta de proyecto en línea.
 */
export const PROJECTS: Project[] = [
  { id: 'p1', tenant_id: 't1', name: 'Atención', slug: 'atencion', status: 'active' },
  { id: 'p2', tenant_id: 't2', name: 'Ventas', slug: 'ventas', status: 'active' },
]

export const AGENTS: Agent[] = [
  { id: 'a1', project_id: 'p1', name: 'Recepción', langflow_flow_id: 'f1', is_default: true, status: 'active' },
  { id: 'a1b', project_id: 'p1', name: 'Citas', langflow_flow_id: 'f1b', is_default: false, status: 'active' },
  { id: 'a2', project_id: 'p2', name: 'Asesor', langflow_flow_id: 'f2', is_default: true, status: 'active' },
]

const now = '2026-09-01T10:00:00Z'
const conn = (o: Partial<ChannelConnection> & Pick<ChannelConnection, 'id' | 'project_id' | 'agent_id' | 'channel_type' | 'external_id'>): ChannelConnection => ({
  display_name: null,
  has_credentials: false,
  config: {},
  status: 'active',
  created_at: now,
  updated_at: now,
  ...o,
})

export const CONNECTIONS: ChannelConnection[] = [
  conn({ id: 'c1', project_id: 'p1', agent_id: 'a1', channel_type: 'whatsapp_evolution', external_id: 'vital-wa', display_name: 'WhatsApp Clínica' }),
  conn({ id: 'c2', project_id: 'p1', agent_id: 'a1b', channel_type: 'telegram', external_id: '123456789:SECRETTOKEN', display_name: 'Bot de citas', has_credentials: true }),
  conn({ id: 'c3', project_id: 'p2', agent_id: 'a2', channel_type: 'instagram', external_id: '17841400000000', display_name: 'Instagram Norte', has_credentials: true, status: 'inactive' }),
]

export const SEED = { projects: PROJECTS, agents: AGENTS, connections: CONNECTIONS }
