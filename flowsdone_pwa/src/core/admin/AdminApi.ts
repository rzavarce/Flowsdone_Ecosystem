import type {
  Agent,
  ChannelApp,
  ChannelAppProvider,
  ChannelConnection,
  CreateChannelConnectionInput,
  CreateProjectInput,
  CreateTenantInput,
  Project,
  TenantRecord,
  UpdateChannelConnectionInput,
  UpdateProjectInput,
  UpdateTenantInput,
  LangflowSession,
} from './types'

/**
 * Puerto de la API de administración. La UI solo conoce esta interfaz; hay un
 * adaptador HTTP (gateway real) y uno mock (desarrollo/maquetas).
 *
 * Todo lo que devuelve ya viene filtrado por lo que el perfil puede ver: el
 * gateway aplica el rol y el alcance por tenant (lo ajeno responde 404).
 */
export interface AdminApi {
  /** Tenants visibles (todos para un admin; solo los propios para el resto). */
  listTenants(): Promise<TenantRecord[]>
  /** Solo admin. */
  createTenant(input: CreateTenantInput): Promise<TenantRecord>
  /** Solo admin. `status: 'suspended'` corta el enrutado de todos sus canales. */
  updateTenant(id: string, patch: UpdateTenantInput): Promise<TenantRecord>
  /** Solo admin. Borra EN CASCADA sus proyectos, agentes y canales. */
  deleteTenant(id: string): Promise<void>

  /** Proyectos visibles, opcionalmente de un tenant. */
  listProjects(tenantId?: string): Promise<Project[]>
  createProject(input: CreateProjectInput): Promise<Project>
  updateProject(id: string, patch: UpdateProjectInput): Promise<Project>
  /** Borra EN CASCADA sus agentes y canales. */
  deleteProject(id: string): Promise<void>

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

  /**
   * Solo admin. Prepara el Langflow del tenant (su usuario y una carpeta por proyecto)
   * y devuelve la URL de inicio de sesión única para el iframe. Con `projectId` abre
   * la carpeta de ese proyecto; sin él, la del primero.
   */
  createLangflowSession(tenantId: string, projectId?: string): Promise<LangflowSession>
}
