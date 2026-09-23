import { FolderKanban, Pause, Pencil, Play, Plus, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Project } from '@/core/admin/types'
import { summarize, type ProjectCounts } from './useTenantsView'

/** Props for {@link ProjectsCard}. */
export interface ProjectsCardProps {
  projects: Project[]
  counts: Map<string, ProjectCounts>
  onCreate: () => void
  onEdit: (project: Project) => void
  /** Suspends or reactivates (toggles based on the current status). */
  onToggleStatus: (project: Project) => void
  onDelete: (project: Project) => void
}

/** Projects of the selected tenant, with status, content and actions. */
export function ProjectsCard({ projects, counts, onCreate, onEdit, onToggleStatus, onDelete }: ProjectsCardProps) {
  return (
    <Card>
      <CardHeader
        title="Proyectos"
        description="Cada canal y cada agente pertenece a un proyecto."
        action={
          <Button size="sm" onClick={onCreate}>
            <Plus className="size-4" aria-hidden="true" />
            Nuevo proyecto
          </Button>
        }
      />
      {projects.length === 0 ? (
        <div className="p-5">
          <EmptyState icon={FolderKanban} title="Este tenant aún no tiene proyectos" description="Crea el primero para poder conectar canales y agentes." />
        </div>
      ) : (
        <ul className="mt-4 divide-y divide-border border-t border-border">
          {projects.map((project) => {
            const c = counts.get(project.id) ?? { agents: 0, channels: 0 }
            const active = project.status === 'active'
            return (
              <li key={project.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium">
                    <span className="truncate">{project.name}</span>
                    {!active && <Badge tone="warning">Suspendido</Badge>}
                  </p>
                  <p className="truncate font-mono text-xs text-muted">{project.slug}</p>
                  <p className="mt-1 text-xs text-muted">{summarize(c)}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" onClick={() => onEdit(project)} aria-label={`Editar ${project.name}`}>
                    <Pencil className="size-4" aria-hidden="true" />
                    Editar
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onToggleStatus(project)} aria-label={`${active ? 'Suspender' : 'Reactivar'} ${project.name}`}>
                    {active ? <Pause className="size-4" aria-hidden="true" /> : <Play className="size-4" aria-hidden="true" />}
                    {active ? 'Suspender' : 'Reactivar'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => onDelete(project)} aria-label={`Eliminar ${project.name}`}>
                    <Trash2 className="size-4" aria-hidden="true" />
                    Eliminar
                  </Button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
