import { Plus, Users as UsersIcon } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useDeleteUser, useResendUserActivation, useUsers } from '@/core/admin/hooks'
import type { UserRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { UserDialog } from './UserDialog'
import { UserList } from './UserList'

/** Diálogo abierto: usuario nuevo/editado, o ninguno. */
type Dialog = { user: UserRecord | null } | null

/**
 * Usuarios de consola: alta, edición y borrado de `admin`, `tenant_manager`
 * y `botmaster` (solo admin). Los `client` no aparecen aquí - se crean y se
 * ven junto a su tenant, en la pantalla Tenants.
 */
export function UsersPage() {
  const users = useUsers()
  const deleteUser = useDeleteUser()
  const resendActivation = useResendUserActivation()
  const [dialog, setDialog] = useState<Dialog>(null)
  const [toDelete, setToDelete] = useState<UserRecord | null>(null)
  // Único feedback de "reenviar activación": no cambia nada visible en la fila
  // (sigue pending haya ido bien o mal), así que sin esto no hay forma de saber
  // si se mandó. Se reemplaza con el siguiente intento, no hace falta cerrarlo a mano.
  const [resendFeedback, setResendFeedback] = useState<{ userId: string; tone: 'success' | 'danger'; message: string } | null>(null)

  const staff = (users.data ?? []).filter((u) => u.role !== 'client')

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
      setResendFeedback({ userId: user.id, tone: 'success', message: `Se reenvió el email de activación a ${user.email}.` })
    } catch (err) {
      setResendFeedback({ userId: user.id, tone: 'danger', message: describeError(err) })
    }
  }

  return (
    <div>
      <PageHeader
        title="Usuarios"
        description="Administradores, gestores de tenant y botmasters de la plataforma."
        actions={
          <Button onClick={() => setDialog({ user: null })}>
            <Plus className="size-4" aria-hidden="true" />
            Nuevo usuario
          </Button>
        }
      />

      {resendFeedback && (
        <Alert tone={resendFeedback.tone} className="mb-4" onDismiss={() => setResendFeedback(null)}>
          {resendFeedback.message}
        </Alert>
      )}

      {users.isPending ? (
        <Spinner label="Cargando usuarios" className="py-20" />
      ) : users.isError ? (
        <Alert tone="danger">{describeError(users.error)}</Alert>
      ) : staff.length === 0 ? (
        <EmptyState icon={UsersIcon} title="Aún no hay usuarios" description="Crea el primero para empezar a repartir accesos." />
      ) : (
        <UserList
          users={staff}
          onEdit={(user) => setDialog({ user })}
          onDelete={setToDelete}
          onResendActivation={handleResendActivation}
          resendingId={resendActivation.isPending ? resendActivation.variables : undefined}
        />
      )}

      {dialog && <UserDialog user={dialog.user} onClose={() => setDialog(null)} />}

      <ConfirmDialog
        open={toDelete !== null}
        title="Eliminar usuario"
        description={toDelete ? `Se eliminará a ${toDelete.name} (${toDelete.email}) y se cerrarán todas sus sesiones activas.` : ''}
        confirmLabel="Eliminar"
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
