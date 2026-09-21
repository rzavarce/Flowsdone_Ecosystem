import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  ChannelAppProvider,
  CreateChannelConnectionInput,
  CreateProjectInput,
  UpdateChannelConnectionInput,
} from './types'
import { useAdminApi } from './useAdminApi'

/** Claves de caché. Agrupadas para invalidar de forma coherente tras una mutación. */
export const adminKeys = {
  projects: ['projects'] as const,
  agents: ['agents'] as const,
  connections: ['channel-connections'] as const,
  apps: ['channel-apps'] as const,
}

/** Proyectos visibles; con `tenantId` solo los de ese tenant. */
export function useProjects(tenantId?: string) {
  const api = useAdminApi()
  return useQuery({ queryKey: [...adminKeys.projects, tenantId ?? 'all'], queryFn: () => api.listProjects(tenantId) })
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
