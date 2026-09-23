import { LoaderCircle, Mail, Pencil, Trash2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Avatar } from '@/components/ui/Avatar'
import { Badge, type BadgeTone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ROLE_META } from '@/core/auth/permissions'
import type { UserRecord } from '@/core/admin/types'
import { useAdminApi } from '@/core/admin/useAdminApi'

const STATUS_TONE: Record<UserRecord['status'], BadgeTone> = {
  active: 'success',
  pending: 'warning',
  disabled: 'neutral',
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
  const { t } = useTranslation()
  const api = useAdminApi()
  return (
    <Card className="overflow-hidden">
      <ul aria-label={t('nav.users')} className="divide-y divide-border">
        {users.map((user) => {
          return (
            <li key={user.id} className="flex items-center gap-3 px-4 py-3.5">
              <Avatar name={user.name} src={api.userAvatarUrl(user)} className="size-10" />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="truncate font-medium">{user.name}</span>
                  <Badge tone="primary">{ROLE_META[user.role].label}</Badge>
                  <Badge tone={STATUS_TONE[user.status]}>{t(`users.status.${user.status}`)}</Badge>
                </span>
                <span className="block truncate text-xs text-muted">{user.email}</span>
                {user.role !== 'admin' && (
                  <span className="block text-xs text-muted">
                    {t('users.tenantCount', { count: user.tenant_ids.length })}
                  </span>
                )}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {user.status === 'pending' && (
                  <Button
                    variant="ghost"
                    size="icon"
                    title={resendingId === user.id ? t('users.resend.pending') : t('users.resend.action')}
                    aria-label={resendingId === user.id ? t('users.resend.pendingItem', { name: user.name }) : t('users.resend.actionItem', { name: user.name })}
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
                <Button variant="ghost" size="icon" title={t('common.edit')} aria-label={t('common.editItem', { name: user.name })} onClick={() => onEdit(user)}>
                  <Pencil className="size-4" aria-hidden="true" />
                </Button>
                <Button variant="ghost" size="icon" title={t('common.delete')} aria-label={t('common.deleteItem', { name: user.name })} onClick={() => onDelete(user)}>
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
