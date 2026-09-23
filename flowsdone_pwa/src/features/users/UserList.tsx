import { LoaderCircle, Mail, Pencil, Trash2, UserRound } from 'lucide-react'
import { Badge, type BadgeTone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ROLE_META } from '@/core/auth/permissions'
import type { UserRecord } from '@/core/admin/types'

const STATUS: Record<UserRecord['status'], { label: string; tone: BadgeTone }> = {
  active: { label: 'Activo', tone: 'success' },
  pending: { label: 'Pendiente de activar', tone: 'warning' },
  disabled: { label: 'Deshabilitado', tone: 'neutral' },
}

/** Props for {@link UserList}. */
export interface UserListProps {
  users: UserRecord[]
  onEdit: (user: UserRecord) => void
  onDelete: (user: UserRecord) => void
  onResendActivation: (user: UserRecord) => void
  /** Id of the user whose activation is being resent (disables that button). */
  resendingId?: string
}

/** List of console users (admin, managers and botmasters) with their actions. */
export function UserList({ users, onEdit, onDelete, onResendActivation, resendingId }: UserListProps) {
  return (
    <Card className="overflow-hidden">
      <ul aria-label="Usuarios" className="divide-y divide-border">
        {users.map((user) => {
          const status = STATUS[user.status]
          return (
            <li key={user.id} className="flex items-center gap-3 px-4 py-3.5">
              <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-primary-ink">
                <UserRound className="size-4.5" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{user.name}</span>
                  <Badge tone="primary">{ROLE_META[user.role].label}</Badge>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </span>
                <span className="block truncate text-xs text-muted">{user.email}</span>
                {user.role !== 'admin' && (
                  <span className="block text-xs text-muted">
                    {user.tenant_ids.length} tenant{user.tenant_ids.length === 1 ? '' : 's'}
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {user.status === 'pending' && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title={resendingId === user.id ? 'Reenviando…' : 'Reenviar email de activación'}
                    aria-label={resendingId === user.id ? `Reenviando activación a ${user.name}` : `Reenviar email de activación a ${user.name}`}
                    disabled={resendingId === user.id}
                    onClick={() => onResendActivation(user)}
                  >
                    {resendingId === user.id ? (
                      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
                    ) : (
                      <Mail className="size-4" aria-hidden="true" />
                    )}
                  </Button>
                )}
                <Button variant="ghost" size="icon" title="Editar" aria-label={`Editar ${user.name}`} onClick={() => onEdit(user)}>
                  <Pencil className="size-4" aria-hidden="true" />
                </Button>
                <Button variant="ghost" size="icon" title="Eliminar" aria-label={`Eliminar ${user.name}`} onClick={() => onDelete(user)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              </span>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
