import { useMemo } from 'react'
import { useAgents, useChannelConnections, useProjects, useTenants } from '@/core/admin/hooks'
import type { Project, TenantRecord } from '@/core/admin/types'

/** How many items hang off a project. */
export interface ProjectCounts {
  agents: number
  channels: number
}

/** A tenant with what it contains, to render the list and warn about cascading deletes. */
export interface TenantEntry {
  tenant: TenantRecord
  projects: Project[]
  agents: number
  channels: number
}

/** Tenants screen data, already combined. */
export interface TenantsView {
  isLoading: boolean
  error: Error | null
  refetch: () => void
  /**
   * Re-fetches projects, agents and channels and awaits the result. Used
   * before confirming a cascading delete, so the warning counts what's
   * there NOW rather than what was in the cache (which can be up to 30 s stale).
   */
  refreshContents: () => Promise<void>
  entries: TenantEntry[]
  /** Agents and channels of each project (keyed by project id). */
  projectCounts: Map<string, ProjectCounts>
}

/**
 * Combines tenants, projects, agents and channels and computes the counts.
 *
 * The gateway already returns only what's visible to the role (a manager
 * only sees their own tenants); the counts come from those same lists,
 * without extra requests.
 */
export function useTenantsView(): TenantsView {
  const tenantsQ = useTenants()
  const projectsQ = useProjects()
  const agentsQ = useAgents()
  const connectionsQ = useChannelConnections()

  return useMemo(() => {
    const projects = projectsQ.data ?? []
    const projectCounts = new Map<string, ProjectCounts>(projects.map((p) => [p.id, { agents: 0, channels: 0 }]))
    for (const a of agentsQ.data ?? []) {
      const c = projectCounts.get(a.project_id)
      if (c) c.agents += 1
    }
    for (const c of connectionsQ.data ?? []) {
      const counts = projectCounts.get(c.project_id)
      if (counts) counts.channels += 1
    }
    const entries = (tenantsQ.data ?? []).map((tenant) => {
      const own = projects.filter((p) => p.tenant_id === tenant.id)
      return {
        tenant,
        projects: own,
        agents: own.reduce((n, p) => n + (projectCounts.get(p.id)?.agents ?? 0), 0),
        channels: own.reduce((n, p) => n + (projectCounts.get(p.id)?.channels ?? 0), 0),
      }
    })
    return {
      isLoading: tenantsQ.isLoading || projectsQ.isLoading || agentsQ.isLoading || connectionsQ.isLoading,
      error: tenantsQ.error ?? projectsQ.error ?? agentsQ.error ?? connectionsQ.error,
      refetch: () => {
        void tenantsQ.refetch()
        void projectsQ.refetch()
        void agentsQ.refetch()
        void connectionsQ.refetch()
      },
      refreshContents: async () => {
        await Promise.all([projectsQ.refetch(), agentsQ.refetch(), connectionsQ.refetch()])
      },
      entries,
      projectCounts,
    }
  }, [tenantsQ, projectsQ, agentsQ, connectionsQ])
}

/** Phrase with the counts, correctly singular/plural (e.g. "1 project · 3 channels"). */
export function summarize({ projects, agents, channels }: { projects?: number; agents: number; channels: number }): string {
  const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
  return [
    projects === undefined ? null : plural(projects, 'proyecto', 'proyectos'),
    plural(agents, 'agente', 'agentes'),
    plural(channels, 'canal', 'canales'),
  ]
    .filter(Boolean)
    .join(' · ')
}
