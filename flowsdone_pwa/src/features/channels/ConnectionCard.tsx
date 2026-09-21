import { Pencil, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import type { ChannelConnection } from '@/core/admin/types'
import { CHANNEL_TYPES, maskExternalId } from './channelTypes'

/** Props de {@link ConnectionCard}. */
export interface ConnectionCardProps {
  connection: ChannelConnection
  /** Contexto a mostrar bajo el nombre (tenant/proyecto). */
  projectLabel: string
  agentName: string
  onEdit: (connection: ChannelConnection) => void
  onDelete: (connection: ChannelConnection) => void
}

/** Tarjeta de un canal conectado: identidad, estado, proyecto/agente y acciones. */
export function ConnectionCard({ connection, projectLabel, agentName, onEdit, onDelete }: ConnectionCardProps) {
  const config = CHANNEL_TYPES[connection.channel_type]
  const Icon = config.icon
  const name = connection.display_name || config.label
  const active = connection.status === 'active'

  return (
    <Card className="flex flex-col p-5 transition hover:border-primary/40">
      <div className="flex items-start gap-3">
        <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl bg-accent text-primary-ink">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-semibold">{name}</h2>
          <p className="truncate text-sm text-muted">{config.label}</p>
        </div>
        <Badge tone={active ? 'success' : 'warning'}>{active ? 'Activo' : 'Inactivo'}</Badge>
      </div>

      <dl className="mt-4 space-y-1.5 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">{config.externalIdLabel}</dt>
          <dd className="min-w-0 truncate font-mono text-xs">{maskExternalId(connection.channel_type, connection.external_id)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Proyecto</dt>
          <dd className="min-w-0 truncate">{projectLabel}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Agente</dt>
          <dd className="min-w-0 truncate">{agentName}</dd>
        </div>
      </dl>

      <div className="mt-5 flex justify-end gap-2 border-t border-border pt-4">
        <Button variant="secondary" size="sm" onClick={() => onEdit(connection)} aria-label={`Editar ${name}`}>
          <Pencil className="size-4" aria-hidden="true" />
          Editar
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(connection)} aria-label={`Eliminar ${name}`}>
          <Trash2 className="size-4" aria-hidden="true" />
          Eliminar
        </Button>
      </div>
    </Card>
  )
}
