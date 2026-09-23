import { useMemo } from 'react'
import { useAgents, useChannelConnections, useProjects } from '@/core/admin/hooks'
import type { Agent, ChannelConnection, Project } from '@/core/admin/types'
import { useTenant } from '@/core/tenant/useTenant'

/** Channels screen data, already combined and scoped to the active tenant. */
export interface ChannelsView {
  isLoading: boolean
  error: Error | null
  refetch: () => void
  /** Projects in the current scope (of the active tenant, or all visible ones). */
  projects: Project[]
  /** All visible agents (the form narrows the list further by project). */
  agents: Agent[]
  /** Connections whose project falls within the current scope. */
  connections: ChannelConnection[]
  projectById: Map<string, Project>
  agentById: Map<string, Agent>
}

/**
 * Combines projects, agents and connections and scopes them to the active tenant.
 *
 * The gateway already returns only what the role can see; this adds the
 * narrowing by the tenant chosen in the selector (or everything, for an
 * admin on "All tenants").
 */
export function useChannelsView(): ChannelsView {
  const { current } = useTenant()
  const projectsQ = useProjects(current?.id)
  const agentsQ = useAgents()
  const connectionsQ = useChannelConnections()

  return useMemo(() => {
    const projects = projectsQ.data ?? []
    const agents = agentsQ.data ?? []
    const inScope = new Set(projects.map((p) => p.id))
    const connections = (connectionsQ.data ?? []).filter((c) => !current || inScope.has(c.project_id))
    return {
      isLoading: projectsQ.isLoading || agentsQ.isLoading || connectionsQ.isLoading,
      error: projectsQ.error ?? agentsQ.error ?? connectionsQ.error,
      refetch: () => {
        void projectsQ.refetch()
        void agentsQ.refetch()
        void connectionsQ.refetch()
      },
      projects,
      agents,
      connections,
      projectById: new Map(projects.map((p) => [p.id, p])),
      agentById: new Map(agents.map((a) => [a.id, a])),
    }
  }, [current, projectsQ, agentsQ, connectionsQ])
}
