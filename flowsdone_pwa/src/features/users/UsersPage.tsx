import { Plus, SearchX, Users as UsersIcon } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useDeleteUser, useResendUserActivation, useUsers } from '@/core/admin/hooks'
import type { UserAccountStatus, UserRecord } from '@/core/admin/types'
import { ROLE_META } from '@/core/auth/permissions'
import { ROLES, type Role } from '@/core/auth/types'
import { describeError } from '@/core/http/describeError'
import { useTenant } from '@/core/tenant/useTenant'
import { matchesQuery } from '@/lib/search'
import { UserDialog } from './UserDialog'
import { UserList } from './UserList'

/** Open dialog: new/edited user, or none. */
type Dialog = { user: UserRecord | null } | null

/** Roles managed from this screen (`client` accounts live with their tenant). */
const STAFF_ROLES = ROLES.filter((r) => r !== 'client')
const STATUSES: UserAccountStatus[] = ['active', 'pending', 'disabled']

/**
 * Console users: create, edit and delete `admin`, `tenant_manager` and
 * `botmaster` (admin only). `client` users don't appear here - they're
 * created and viewed alongside their tenant, in the Tenants screen.
 *
 * The list follows the top bar's tenant selector (with a tenant picked, only
 * that tenant's users - admins belong to none, so they only show under "All
 * tenants") and can be narrowed by name/email, role and status.
 */
export function UsersPage() {
  const { t } = useTranslation()
  const users = useUsers()
  const deleteUser = useDeleteUser()
  const resendActivation = useResendUserActivation()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [toDelete, setToDelete] = useState<UserRecord | null>(null)
  // Único feedback de "reenviar activación": no cambia nada visible en la fila
  // (sigue pending haya ido bien o mal), así que sin esto no hay forma de saber
  // si se mandó. Se reemplaza con el siguiente intento, no hace falta cerrarlo a mano.
  const [resendFeedback, setResendFeedback] = useState<{ userId: string; tone: 'success' | 'danger'; message: string } | null>(null)

  const { current } = useTenant()
  const [query, setQuery] = useState('')
  const [role, setRole] = useState<Role | ''>('')
  const [status, setStatus] = useState<UserAccountStatus | ''>('')

  const staff = (users.data ?? []).filter((u) => u.role !== 'client')
  const visible = staff.filter(
    (u) =>
      (!current || u.tenant_ids.includes(current.id)) &&
      (!role || u.role === role) &&
      (!status || u.status === status) &&
      matchesQuery(query, u.name, u.email),
  )

  async function confirmDelete() {
    if (!toDelete) return
    try {
      await deleteUser.mutateAsync(toDelete.id)
      setToDelete(null)
    } catch {
      // El error queda en deleteUser.error y se muestra en el diálogo.
    }
  }

  async function handleResendActivation(user: UserRecord) {
    setResendFeedback(null)
    try {
      await resendActivation.mutateAsync(user.id)
      setResendFeedback({ userId: user.id, tone: 'success', message: t('users.resend.done', { email: user.email }) })
    } catch (err) {
      setResendFeedback({ userId: user.id, tone: 'danger', message: describeError(err) })
    }
  }

  return (
    <div>
      <PageHeader
        title={t('nav.users')}
        description={t('users.description')}
        actions={
          <Button onClick={() => setDialog({ user: null })}>
            <Plus className="size-4" aria-hidden="true" />
            {t('users.new')}
          </Button>
        }
      />

      {resendFeedback && (
        <Alert tone={resendFeedback.tone} className="mb-4" onDismiss={() => setResendFeedback(null)}>
          {resendFeedback.message}
        </Alert>
      )}

      {users.isPending ? (
        <Spinner label={t('users.loading')} className="py-20" />
      ) : users.isError ? (
        <Alert tone="danger">{describeError(users.error)}</Alert>
      ) : staff.length === 0 ? (
        <EmptyState icon={UsersIcon} title={t('users.empty.title')} description={t('users.empty.description')} />
      ) : (
        <div className="space-y-4">
          <Card className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-[1fr_12rem_12rem]" role="search" aria-label={t('users.filters.label')}>
            <Input
              type="search"
              aria-label={t('users.filters.search')}
              placeholder={t('users.filters.searchPlaceholder')}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Select aria-label={t('users.filters.role')} value={role} onChange={(e) => setRole(e.target.value as Role | '')}>
              <option value="">{t('users.filters.allRoles')}</option>
              {STAFF_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_META[r].label}
                </option>
              ))}
            </Select>
            <Select aria-label={t('users.filters.status')} value={status} onChange={(e) => setStatus(e.target.value as UserAccountStatus | '')}>
              <option value="">{t('users.filters.allStatuses')}</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {t(`users.status.${s}`)}
                </option>
              ))}
            </Select>
          </Card>
          {current && <p className="text-sm text-muted">{t('users.scopedTo', { name: current.name })}</p>}
          {visible.length === 0 ? (
            <EmptyState icon={SearchX} title={t('users.noMatches.title')} description={t('users.noMatches.description')} />
          ) : (
            <UserList
              users={visible}
              onEdit={(user) => setDialog({ user })}
              onDelete={setToDelete}
              onResendActivation={handleResendActivation}
              resendingId={resendActivation.isPending ? resendActivation.variables : undefined}
            />
          )}
        </div>
      )}

      {dialog && <UserDialog user={dialog.user} onClose={() => setDialog(null)} />}

      <ConfirmDialog
        open={toDelete !== null}
        title={t('users.delete.title')}
        description={toDelete ? t('users.delete.description', { name: toDelete.name, email: toDelete.email }) : ''}
        confirmLabel={t('common.delete')}
        pending={deleteUser.isPending}
        error={deleteUser.error ? describeError(deleteUser.error) : null}
        onConfirm={confirmDelete}
        onCancel={() => {
          deleteUser.reset()
          setToDelete(null)
        }}
      />
    </div>
  )
}
