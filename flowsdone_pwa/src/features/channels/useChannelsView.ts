import { useMemo } from 'react'
import { useAgents, useChannelConnections, useProjects } from '@/core/admin/hooks'
import type { Agent, ChannelConnection, Project } from '@/core/admin/types'
import { useTenant } from '@/core/tenant/useTenant'

/** Datos de la pantalla de Canales ya combinados y acotados al tenant activo. */
export interface ChannelsView {
  isLoading: boolean
  error: Error | null
  refetch: () => void
  /** Proyectos del alcance actual (del tenant activo, o todos los visibles). */
  projects: Project[]
  /** Todos los agentes visibles (la lista se acota por proyecto en el formulario). */
  agents: Agent[]
  /** Conexiones cuyo proyecto está dentro del alcance actual. */
  connections: ChannelConnection[]
  projectById: Map<string, Project>
  agentById: Map<string, Agent>
}

/**
 * Reúne proyectos, agentes y conexiones y los limita al tenant activo.
 *
 * El gateway ya devuelve solo lo que el perfil puede ver; acá se añade el
 * recorte por el tenant elegido en el selector (o todo, para un admin en
 * "Todos los tenants").
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
