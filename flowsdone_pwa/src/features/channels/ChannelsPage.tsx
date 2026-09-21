import { Plug, Plus } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useDeleteConnection } from '@/core/admin/hooks'
import type { ChannelConnection } from '@/core/admin/types'
import { useTenant } from '@/core/tenant/useTenant'
import { CHANNEL_TYPES } from './channelTypes'
import { ConnectionCard } from './ConnectionCard'
import { ConnectionDialog } from './ConnectionDialog'
import { describeError } from '@/core/http/describeError'
import { useChannelsView } from './useChannelsView'

/** Qué diálogo está abierto: crear, editar una conexión, o ninguno. */
type DialogState = { kind: 'create' } | { kind: 'edit'; connection: ChannelConnection } | null

/**
 * Canales conectados del tenant activo: lista, alta, edición y baja.
 *
 * Los datos vienen del gateway ya limitados a lo que el perfil puede ver; acá
 * se recorta además por el tenant elegido en el selector.
 */
export function ChannelsPage() {
  const view = useChannelsView()
  const { current, tenants } = useTenant()
  const remove = useDeleteConnection()
  const [dialog, setDialog] = useState<DialogState>(null)
  const [toDelete, setToDelete] = useState<ChannelConnection | null>(null)

  const tenantName = new Map(tenants.map((t) => [t.id, t.name]))
  const projectLabel = (projectId: string) => {
    const project = view.projectById.get(projectId)
    if (!project) return '—'
    // Con "Todos los tenants" hace falta el tenant para distinguir proyectos homónimos.
    return current ? project.name : `${tenantName.get(project.tenant_id) ?? 'Tenant'} · ${project.name}`
  }

  async function confirmDelete() {
    if (!toDelete) return
    try {
      await remove.mutateAsync(toDelete.id)
      setToDelete(null)
    } catch {
      // El error se muestra en el diálogo (remove.error).
    }
  }

  const actions = (
    <Button onClick={() => setDialog({ kind: 'create' })} disabled={view.isLoading}>
      <Plus className="size-4" aria-hidden="true" />
      Nuevo canal
    </Button>
  )

  return (
    <>
      <PageHeader
        title="Canales"
        description={current ? `Canales conectados de ${current.name}.` : 'Canales conectados de todos los tenants.'}
        actions={actions}
      />

      {view.isLoading ? (
        <Spinner label="Cargando canales" className="py-20" />
      ) : view.error ? (
        <Alert tone="danger">
          <p>No se pudieron cargar los canales: {describeError(view.error)}</p>
          <Button variant="secondary" size="sm" className="mt-3" onClick={view.refetch}>
            Reintentar
          </Button>
        </Alert>
      ) : view.connections.length === 0 ? (
        <EmptyState
          icon={Plug}
          title="Aún no hay canales conectados"
          description="Conecta WhatsApp, Telegram, Instagram u otro canal para que un agente empiece a responder."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {view.connections.map((connection) => (
            <ConnectionCard
              key={connection.id}
              connection={connection}
              projectLabel={projectLabel(connection.project_id)}
              agentName={view.agentById.get(connection.agent_id)?.name ?? '—'}
              onEdit={(c) => setDialog({ kind: 'edit', connection: c })}
              onDelete={(c) => {
                remove.reset()
                setToDelete(c)
              }}
            />
          ))}
        </div>
      )}

      {dialog && (
        <ConnectionDialog
          connection={dialog.kind === 'edit' ? dialog.connection : null}
          view={view}
          onClose={() => setDialog(null)}
        />
      )}

      <ConfirmDialog
        open={toDelete !== null}
        title={toDelete ? `Eliminar ${toDelete.display_name || CHANNEL_TYPES[toDelete.channel_type].label}` : ''}
        description="El agente dejará de recibir y responder mensajes por este canal. Para Telegram, Flowsdone también intentará quitar el webhook."
        confirmLabel="Eliminar canal"
        pending={remove.isPending}
        error={remove.error ? describeError(remove.error) : null}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  )
}
