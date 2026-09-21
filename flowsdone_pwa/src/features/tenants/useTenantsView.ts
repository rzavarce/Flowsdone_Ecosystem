import { useMemo } from 'react'
import { useAgents, useChannelConnections, useProjects, useTenants } from '@/core/admin/hooks'
import type { Project, TenantRecord } from '@/core/admin/types'

/** Cuántos elementos cuelgan de un proyecto. */
export interface ProjectCounts {
  agents: number
  channels: number
}

/** Un tenant con lo que hay dentro, para pintar la lista y avisar de borrados en cascada. */
export interface TenantEntry {
  tenant: TenantRecord
  projects: Project[]
  agents: number
  channels: number
}

/** Datos de la pantalla Tenants ya combinados. */
export interface TenantsView {
  isLoading: boolean
  error: Error | null
  refetch: () => void
  /**
   * Vuelve a pedir proyectos, agentes y canales y espera el resultado. Se usa antes de
   * confirmar un borrado en cascada, para que el aviso cuente lo que hay AHORA y no lo
   * que había en la caché (que puede tener hasta 30 s).
   */
  refreshContents: () => Promise<void>
  entries: TenantEntry[]
  /** Agentes y canales de cada proyecto (por id de proyecto). */
  projectCounts: Map<string, ProjectCounts>
}

/**
 * Reúne tenants, proyectos, agentes y canales y calcula los recuentos.
 *
 * El gateway ya devuelve solo lo visible para el perfil (un gestor solo ve sus
 * tenants); los recuentos salen de las mismas listas, sin peticiones extra.
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

/** Frase con los recuentos, en singular/plural correctos (p. ej. "1 proyecto · 3 canales"). */
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
