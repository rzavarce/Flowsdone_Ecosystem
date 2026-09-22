import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/core/auth/useAuth'
import type {
  ChannelAppProvider,
  CreateChannelConnectionInput,
  CreateProjectInput,
  CreateTenantInput,
  UpdateChannelConnectionInput,
  UpdateProjectInput,
  UpdateTenantInput,
} from './types'
import { useAdminApi } from './useAdminApi'

/** Claves de caché. Agrupadas para invalidar de forma coherente tras una mutación. */
export const adminKeys = {
  tenants: ['tenants'] as const,
  projects: ['projects'] as const,
  agents: ['agents'] as const,
  connections: ['channel-connections'] as const,
  apps: ['channel-apps'] as const,
  langflowSession: ['langflow-session'] as const,
}

/** Tenants visibles con todos sus datos (slug, estado…). */
export function useTenants() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.tenants, queryFn: () => api.listTenants() })
}

/** Proyectos visibles; con `tenantId` solo los de ese tenant. */
export function useProjects(tenantId?: string) {
  const api = useAdminApi()
  return useQuery({ queryKey: [...adminKeys.projects, tenantId ?? 'all'], queryFn: () => api.listProjects(tenantId) })
}

/**
 * Invalida lo que un borrado en cascada pudo dejar obsoleto (proyectos, agentes y canales).
 * @param qc - El cliente de caché.
 */
function invalidateTree(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all([adminKeys.projects, adminKeys.agents, adminKeys.connections].map((queryKey) => qc.invalidateQueries({ queryKey })))
}

/** Crea un tenant, refresca la lista y el selector de tenant de la sesión. */
export function useCreateTenant() {
  const api = useAdminApi()
  const qc = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn: (input: CreateTenantInput) => api.createTenant(input),
    onSuccess: async () => {
      await Promise.all([qc.invalidateQueries({ queryKey: adminKeys.tenants }), refreshUser()])
    },
  })
}

/** Edita o suspende/reactiva un tenant. */
export function useUpdateTenant() {
  const api = useAdminApi()
  const qc = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateTenantInput }) => api.updateTenant(id, patch),
    onSuccess: async () => {
      await Promise.all([qc.invalidateQueries({ queryKey: adminKeys.tenants }), refreshUser()])
    },
  })
}

/** Borra un tenant (en cascada) y refresca todo lo que colgaba de él. */
export function useDeleteTenant() {
  const api = useAdminApi()
  const qc = useQueryClient()
  const { refreshUser } = useAuth()
  return useMutation({
    mutationFn: (id: string) => api.deleteTenant(id),
    onSuccess: async () => {
      await Promise.all([qc.invalidateQueries({ queryKey: adminKeys.tenants }), invalidateTree(qc), refreshUser()])
    },
  })
}

/** Edita o suspende/reactiva un proyecto. */
export function useUpdateProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateProjectInput }) => api.updateProject(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.projects }),
  })
}

/** Borra un proyecto (en cascada: agentes y canales). */
export function useDeleteProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => invalidateTree(qc),
  })
}

/** Agentes visibles para el perfil. */
export function useAgents() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.agents, queryFn: () => api.listAgents() })
}

/** Conexiones de canal visibles para el perfil. */
export function useChannelConnections() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.connections, queryFn: () => api.listChannelConnections() })
}

/** Crea un proyecto y refresca la lista. */
export function useCreateProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateProjectInput) => api.createProject(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.projects }),
  })
}

/** Crea una conexión de canal y refresca la lista. */
export function useCreateConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateChannelConnectionInput) => api.createChannelConnection(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Edita una conexión de canal y refresca la lista. */
export function useUpdateConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateChannelConnectionInput }) =>
      api.updateChannelConnection(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Borra una conexión de canal y refresca la lista. */
export function useDeleteConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteChannelConnection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Apps compartidas de los proveedores. `enabled` evita pedirlas a perfiles sin permiso. */
export function useChannelApps(enabled = true) {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.apps, queryFn: () => api.listChannelApps(), enabled })
}

/** Crea o reemplaza las credenciales de un proveedor. */
export function useUpsertChannelApp() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, credentials }: { provider: ChannelAppProvider; credentials: Record<string, string> }) =>
      api.upsertChannelApp(provider, credentials),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.apps }),
  })
}

/** Elimina las credenciales de un proveedor. */
export function useDeleteChannelApp() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: ChannelAppProvider) => api.deleteChannelApp(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.apps }),
  })
}

/**
 * Revela las credenciales en claro de un proveedor. Es una mutación (no una
 * consulta) a propósito: no se cachea ni se repite sola; el resultado vive solo
 * en el estado del componente que la pidió.
 */
export function useRevealChannelApp() {
  const api = useAdminApi()
  return useMutation({ mutationFn: (provider: ChannelAppProvider) => api.revealChannelAppCredentials(provider) })
}

/**
 * URL de inicio de sesión única de Langflow para un tenant (y, opcional, un proyecto).
 *
 * El ticket que lleva se consume una sola vez y caduca en segundos, por eso nunca se
 * reutiliza desde la caché (`gcTime: 0`) ni se refresca solo mientras el editor está
 * abierto (`staleTime: Infinity`): recargarlo dejaría el iframe con un enlace ya usado.
 */
export function useLangflowSession(tenantId?: string, projectId?: string) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...adminKeys.langflowSession, tenantId, projectId],
    queryFn: () => api.createLangflowSession(tenantId as string, projectId),
    enabled: Boolean(tenantId),
    staleTime: Infinity,
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}
