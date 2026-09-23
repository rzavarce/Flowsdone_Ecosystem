import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/core/auth/useAuth'
import type {
  ChannelAppProvider,
  CreateChannelConnectionInput,
  CreateProjectInput,
  CreateTenantInput,
  CreateUserInput,
  UpdateChannelConnectionInput,
  UpdateProjectInput,
  UpdateTenantBillingInput,
  UpdateTenantInput,
  UpdateUserInput,
} from './types'
import { useAdminApi } from './useAdminApi'

/** Cache keys. Grouped so mutations can invalidate related data consistently. */
export const adminKeys = {
  tenants: ['tenants'] as const,
  tenantBilling: ['tenant-billing'] as const,
  projects: ['projects'] as const,
  agents: ['agents'] as const,
  connections: ['channel-connections'] as const,
  apps: ['channel-apps'] as const,
  users: ['users'] as const,
  langflowSession: ['langflow-session'] as const,
}

/** Visible tenants with all of their data (slug, status…). */
export function useTenants() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.tenants, queryFn: () => api.listTenants() })
}

/** Visible projects; with `tenantId`, only that tenant's. */
export function useProjects(tenantId?: string) {
  const api = useAdminApi()
  return useQuery({ queryKey: [...adminKeys.projects, tenantId ?? 'all'], queryFn: () => api.listProjects(tenantId) })
}

/**
 * Invalidates whatever a cascade delete may have left stale (projects, agents and channels).
 * @param qc - The cache client.
 */
function invalidateTree(qc: ReturnType<typeof useQueryClient>) {
  return Promise.all([adminKeys.projects, adminKeys.agents, adminKeys.connections].map((queryKey) => qc.invalidateQueries({ queryKey })))
}

/** Creates a tenant, then refreshes the list and the session's tenant selector. */
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

/** Edits or suspends/reactivates a tenant. */
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

/** Deletes a tenant (cascading) and refreshes everything that hung off it. */
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

/** A tenant's billing profile (admin/tenant_manager). Empty (not an error) if nothing was ever saved. */
export function useTenantBilling(tenantId?: string) {
  const api = useAdminApi()
  return useQuery({
    queryKey: [...adminKeys.tenantBilling, tenantId],
    queryFn: () => api.getTenantBilling(tenantId as string),
    enabled: Boolean(tenantId),
  })
}

/** Creates or updates a tenant's billing profile. */
export function useUpdateTenantBilling() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ tenantId, patch }: { tenantId: string; patch: UpdateTenantBillingInput }) =>
      api.updateTenantBilling(tenantId, patch),
    onSuccess: (_data, { tenantId }) =>
      qc.invalidateQueries({ queryKey: [...adminKeys.tenantBilling, tenantId] }),
  })
}

/** Console users (includes `client` accounts; the Users screen filters them out). */
export function useUsers() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.users, queryFn: () => api.listUsers() })
}

/** Creates a user: stays `pending` and gets sent the activation email. */
export function useCreateUser() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateUserInput) => api.createUser(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.users }),
  })
}

/** Edits a user's role, tenants or status. */
export function useUpdateUser() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateUserInput }) => api.updateUser(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.users }),
  })
}

/** Deletes a user and closes all of their sessions. */
export function useDeleteUser() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.users }),
  })
}

/** Resends the activation email for a user that's still `pending`. */
export function useResendUserActivation() {
  const api = useAdminApi()
  return useMutation({ mutationFn: (id: string) => api.resendUserActivation(id) })
}

/** Edits or suspends/reactivates a project. */
export function useUpdateProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateProjectInput }) => api.updateProject(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.projects }),
  })
}

/** Deletes a project (cascading: agents and channels). */
export function useDeleteProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: () => invalidateTree(qc),
  })
}

/** Agents visible to the current profile. */
export function useAgents() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.agents, queryFn: () => api.listAgents() })
}

/** Channel connections visible to the current profile. */
export function useChannelConnections() {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.connections, queryFn: () => api.listChannelConnections() })
}

/** Creates a project and refreshes the list. */
export function useCreateProject() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateProjectInput) => api.createProject(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.projects }),
  })
}

/** Creates a channel connection and refreshes the list. */
export function useCreateConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateChannelConnectionInput) => api.createChannelConnection(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Edits a channel connection and refreshes the list. */
export function useUpdateConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: UpdateChannelConnectionInput }) =>
      api.updateChannelConnection(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Deletes a channel connection and refreshes the list. */
export function useDeleteConnection() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteChannelConnection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.connections }),
  })
}

/** Providers' shared apps. `enabled` avoids requesting them for profiles without permission. */
export function useChannelApps(enabled = true) {
  const api = useAdminApi()
  return useQuery({ queryKey: adminKeys.apps, queryFn: () => api.listChannelApps(), enabled })
}

/** Creates or replaces a provider's credentials. */
export function useUpsertChannelApp() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ provider, credentials }: { provider: ChannelAppProvider; credentials: Record<string, string> }) =>
      api.upsertChannelApp(provider, credentials),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.apps }),
  })
}

/** Removes a provider's credentials. */
export function useDeleteChannelApp() {
  const api = useAdminApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (provider: ChannelAppProvider) => api.deleteChannelApp(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.apps }),
  })
}

/**
 * Reveals a provider's credentials in plaintext. It's deliberately a mutation
 * (not a query): it isn't cached or refetched on its own; the result lives
 * only in the state of the component that requested it.
 */
export function useRevealChannelApp() {
  const api = useAdminApi()
  return useMutation({ mutationFn: (provider: ChannelAppProvider) => api.revealChannelAppCredentials(provider) })
}

/**
 * Single-sign-on Langflow URL for a tenant (and, optionally, a project).
 *
 * The ticket it carries is consumed once and expires within seconds, so it's
 * never reused from the cache (`gcTime: 0`) nor refetched on its own while the
 * editor stays open (`staleTime: Infinity`): reloading it would leave the
 * iframe with an already-used link.
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
