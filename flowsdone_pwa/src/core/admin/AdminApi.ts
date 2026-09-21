import type {
  Agent,
  ChannelApp,
  ChannelAppProvider,
  ChannelConnection,
  CreateChannelConnectionInput,
  CreateProjectInput,
  Project,
  UpdateChannelConnectionInput,
} from './types'

/**
 * Puerto de la API de administración. La UI solo conoce esta interfaz; hay un
 * adaptador HTTP (gateway real) y uno mock (desarrollo/maquetas).
 *
 * Todo lo que devuelve ya viene filtrado por lo que el perfil puede ver: el
 * gateway aplica el rol y el alcance por tenant (lo ajeno responde 404).
 */
export interface AdminApi {
  /** Proyectos visibles, opcionalmente de un tenant. */
  listProjects(tenantId?: string): Promise<Project[]>
  createProject(input: CreateProjectInput): Promise<Project>

  /** Agentes visibles, opcionalmente de un proyecto. */
  listAgents(projectId?: string): Promise<Agent[]>

  /** Conexiones de canal visibles, opcionalmente de un proyecto. */
  listChannelConnections(projectId?: string): Promise<ChannelConnection[]>
  createChannelConnection(input: CreateChannelConnectionInput): Promise<ChannelConnection>
  updateChannelConnection(id: string, patch: UpdateChannelConnectionInput): Promise<ChannelConnection>
  deleteChannelConnection(id: string): Promise<void>

  /** Apps compartidas de los proveedores (solo admin). */
  listChannelApps(): Promise<ChannelApp[]>
  /** Crea o REEMPLAZA las credenciales de un proveedor (solo admin). */
  upsertChannelApp(provider: ChannelAppProvider, credentials: Record<string, string>): Promise<ChannelApp>
  deleteChannelApp(provider: ChannelAppProvider): Promise<void>
  /** Revela las credenciales en claro de un proveedor (solo admin). Úsese con cuidado. */
  revealChannelAppCredentials(provider: ChannelAppProvider): Promise<Record<string, unknown>>
}
