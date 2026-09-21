import { Bot } from 'lucide-react'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useAgents, useProjects } from '@/core/admin/hooks'
import { useTenant } from '@/core/tenant/useTenant'

/**
 * Agentes del tenant activo (solo lectura).
 *
 * Los datos salen del gateway, que ya limita lo visible por rol y tenant; acá se
 * recorta además por el tenant elegido en el selector. La edición visual de
 * flujos no está disponible para este perfil (ver `AgentsPage`).
 */
export function TenantAgents() {
  const { current } = useTenant()
  const projects = useProjects(current?.id)
  const agents = useAgents()

  const info = (
    <Alert tone="info" className="mb-6">
      El editor visual de flujos (Langflow) es solo para el equipo de la plataforma: contiene los agentes de todos los clientes.
      Para crear o cambiar un agente, pídeselo a ese equipo.
    </Alert>
  )

  if (projects.isLoading || agents.isLoading) return <Spinner label="Cargando agentes" className="py-20" />

  const error = projects.error ?? agents.error
  if (error) {
    return (
      <Alert tone="danger">
        <p>No se pudieron cargar los agentes: {error.message}</p>
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          onClick={() => {
            void projects.refetch()
            void agents.refetch()
          }}
        >
          Reintentar
        </Button>
      </Alert>
    )
  }

  const projectById = new Map((projects.data ?? []).map((p) => [p.id, p]))
  const visible = (agents.data ?? []).filter((a) => projectById.has(a.project_id))

  return (
    <>
      {info}
      {visible.length === 0 ? (
        <EmptyState icon={Bot} title="Aún no hay agentes" description="Cuando el equipo de la plataforma cree agentes para tu tenant, aparecerán aquí." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((agent) => (
            <Card key={agent.id} className="p-5">
              <div className="flex items-start gap-3">
                <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent text-primary-ink">
                  <Bot className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate font-semibold">{agent.name}</h2>
                  <p className="truncate text-sm text-muted">{projectById.get(agent.project_id)?.name}</p>
                </div>
                <Badge tone={agent.status === 'active' ? 'success' : 'warning'}>{agent.status === 'active' ? 'Activo' : 'Inactivo'}</Badge>
              </div>
              {agent.is_default && (
                <p className="mt-4 text-xs text-muted">
                  <Badge tone="primary">Por defecto</Badge> responde en los canales de este proyecto que no tengan otro asignado.
                </p>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
