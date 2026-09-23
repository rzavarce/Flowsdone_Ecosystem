import { apiFetch } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import type { Agent, ChannelApp, ChannelConnection, Project, TenantBillingProfile, TenantRecord, UserRecord } from './types'

/**
 * Adapter against the real gateway. In the browser, routes go through
 * `/api/admin/...`, which nginx (or the Vite proxy) forwards to the
 * gateway's `/internal/admin/...`.
 */
export function createHttpAdminApi(fetchFn?: typeof fetch, baseUrl?: string): AdminApi {
  const call = <T>(path: string, method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown) =>
    apiFetch<T>(`/admin${path}`, { method, body, fetchFn, baseUrl })
  const query = (params: Record<string, string | undefined>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][])
    return qs.size ? `?${qs}` : ''
  }

  return {
    listTenants: () => call<TenantRecord[]>('/tenants'),
    createTenant: (input) => call<TenantRecord>('/tenants', 'POST', input),
    updateTenant: (id, patch) => call<TenantRecord>(`/tenants/${id}`, 'PATCH', patch),
    deleteTenant: (id) => call<void>(`/tenants/${id}`, 'DELETE'),
    getTenantBilling: (tenantId) => call<TenantBillingProfile>(`/tenants/${tenantId}/billing`),
    updateTenantBilling: (tenantId, patch) => call<TenantBillingProfile>(`/tenants/${tenantId}/billing`, 'PUT', patch),

    listProjects: (tenantId) => call<Project[]>(`/projects${query({ tenant_id: tenantId })}`),
    createProject: (input) => call<Project>('/projects', 'POST', input),
    updateProject: (id, patch) => call<Project>(`/projects/${id}`, 'PATCH', patch),
    deleteProject: (id) => call<void>(`/projects/${id}`, 'DELETE'),

    listAgents: (projectId) => call<Agent[]>(`/agents${query({ project_id: projectId })}`),

    listChannelConnections: (projectId) =>
      call<ChannelConnection[]>(`/channel-connections${query({ project_id: projectId })}`),
    createChannelConnection: (input) => call<ChannelConnection>('/channel-connections', 'POST', input),
    updateChannelConnection: (id, patch) => call<ChannelConnection>(`/channel-connections/${id}`, 'PATCH', patch),
    deleteChannelConnection: (id) => call<void>(`/channel-connections/${id}`, 'DELETE'),

    listChannelApps: () => call<ChannelApp[]>('/channel-apps'),
    upsertChannelApp: (provider, credentials) => call<ChannelApp>(`/channel-apps/${provider}`, 'PUT', { credentials }),
    deleteChannelApp: (provider) => call<void>(`/channel-apps/${provider}`, 'DELETE'),
    createLangflowSession: (tenantId, projectId) =>
      call('/langflow/session', 'POST', { tenant_id: tenantId, project_id: projectId }),

    revealChannelAppCredentials: async (provider) =>
      (await call<{ credentials: Record<string, unknown> }>(`/channel-apps/${provider}/credentials`)).credentials,

    listUsers: () => call<UserRecord[]>('/users'),
    createUser: (input) => call<UserRecord>('/users', 'POST', input),
    updateUser: (id, patch) => call<UserRecord>(`/users/${id}`, 'PATCH', patch),
    deleteUser: (id) => call<void>(`/users/${id}`, 'DELETE'),
    resendUserActivation: (id) => call<void>(`/users/${id}/resend-activation`, 'POST'),
  }
}
