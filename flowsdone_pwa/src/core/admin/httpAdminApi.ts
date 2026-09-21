import { apiFetch } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import type { Agent, ChannelApp, ChannelConnection, Project } from './types'

/**
 * Adaptador contra el gateway real. En el navegador las rutas van por
 * `/api/admin/...`, que nginx (o el proxy de Vite) reenvía a
 * `/internal/admin/...` del gateway.
 */
export function createHttpAdminApi(fetchFn?: typeof fetch, baseUrl?: string): AdminApi {
  const call = <T>(path: string, method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown) =>
    apiFetch<T>(`/admin${path}`, { method, body, fetchFn, baseUrl })
  const query = (params: Record<string, string | undefined>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][])
    return qs.size ? `?${qs}` : ''
  }

  return {
    listProjects: (tenantId) => call<Project[]>(`/projects${query({ tenant_id: tenantId })}`),
    createProject: (input) => call<Project>('/projects', 'POST', input),

    listAgents: (projectId) => call<Agent[]>(`/agents${query({ project_id: projectId })}`),

    listChannelConnections: (projectId) =>
      call<ChannelConnection[]>(`/channel-connections${query({ project_id: projectId })}`),
    createChannelConnection: (input) => call<ChannelConnection>('/channel-connections', 'POST', input),
    updateChannelConnection: (id, patch) => call<ChannelConnection>(`/channel-connections/${id}`, 'PATCH', patch),
    deleteChannelConnection: (id) => call<void>(`/channel-connections/${id}`, 'DELETE'),

    listChannelApps: () => call<ChannelApp[]>('/channel-apps'),
    upsertChannelApp: (provider, credentials) => call<ChannelApp>(`/channel-apps/${provider}`, 'PUT', { credentials }),
    deleteChannelApp: (provider) => call<void>(`/channel-apps/${provider}`, 'DELETE'),
    revealChannelAppCredentials: async (provider) =>
      (await call<{ credentials: Record<string, unknown> }>(`/channel-apps/${provider}/credentials`)).credentials,
  }
}
