import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateUser, useTenants, useUpdateUser } from '@/core/admin/hooks'
import type { UserRecord } from '@/core/admin/types'
import { ROLE_META } from '@/core/auth/permissions'
import type { Role } from '@/core/auth/types'
import { describeError } from '@/core/http/describeError'

/** Roles que se gestionan desde esta pantalla; `client` se crea desde Tenants. */
const ASSIGNABLE_ROLES: Role[] = ['admin', 'tenant_manager', 'botmaster', 'consultant']

/** Props de {@link UserDialog}. */
export interface UserDialogProps {
  /** `null` = crear un usuario; un usuario = editarlo. */
  user: UserRecord | null
  onClose: () => void
  onSaved?: () => void
}

const FORM_ID = 'user-form'

/**
 * Alta y edición de un usuario `admin`/`tenant_manager`/`botmaster` (solo admin).
 *
 * Sin campo de contraseña: al crear, el usuario queda `pending` y recibe un
 * email para activarse y elegir la suya (ver `ProvisionUserUseCase`). El
 * email tampoco se edita una vez creado (el backend no lo permite).
 */
export function UserDialog({ user, onClose, onSaved }: UserDialogProps) {
  const editing = user !== null
  const tenants = useTenants()
  const create = useCreateUser()
  const update = useUpdateUser()
  const [email, setEmail] = useState(user?.email ?? '')
  const [name, setName] = useState(user?.name ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'botmaster')
  const [active, setActive] = useState(user ? user.status !== 'disabled' : true)
  const [tenantIds, setTenantIds] = useState<string[]>(user?.tenant_ids ?? [])
  const [submitted, setSubmitted] = useState(false)

  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  const needsTenants = role !== 'admin'
  const errors = {
    email: editing || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()) ? '' : 'Escribe un email válido.',
    name: name.trim() ? '' : 'El nombre es obligatorio.',
    tenants: !needsTenants || tenantIds.length > 0 ? '' : 'Elige al menos un tenant.',
  }

  function toggleTenant(id: string) {
    setTenantIds((ids) => (ids.includes(id) ? ids.filter((t) => t !== id) : [...ids, id]))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (errors.email || errors.name || errors.tenants) return
    try {
      if (editing) {
        await update.mutateAsync({
          id: user.id,
          patch: {
            name: name.trim(),
            role,
            status: active ? 'active' : 'disabled',
            tenant_ids: needsTenants ? tenantIds : [],
          },
        })
      } else {
        await create.mutateAsync({
          email: email.trim(),
          name: name.trim(),
          role,
          tenant_ids: needsTenants ? tenantIds : [],
        })
      }
      onSaved?.()
      onClose()
    } catch {
      // El error queda en create.error / update.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={editing ? 'Editar usuario' : 'Nuevo usuario'}
      description={editing ? user.email : 'Se le mandará un email para que active su cuenta y cree su contraseña.'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear usuario'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        {editing ? (
          <Field label="Email">
            <Input value={user.email} disabled />
          </Field>
        ) : (
          <Field label="Email" error={submitted ? errors.email : undefined}>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="persona@flowsdone.com" autoComplete="off" />
          </Field>
        )}

        <Field label="Nombre" error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Nombre completo" />
        </Field>

        <Field label="Rol">
          <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ASSIGNABLE_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_META[r].label}
              </option>
            ))}
          </Select>
        </Field>

        {editing && (
          <Field label="Estado">
            <Select value={active ? 'active' : 'disabled'} onChange={(e) => setActive(e.target.value === 'active')}>
              <option value="active">Activo</option>
              <option value="disabled">Deshabilitado</option>
            </Select>
          </Field>
        )}

        {needsTenants && (
          <div className="space-y-1.5">
            <span className="text-sm font-medium">Tenants</span>
            {tenants.isPending ? (
              <Spinner label="Cargando tenants" />
            ) : (
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-border p-2">
                {(tenants.data ?? []).map((t) => (
                  <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-muted">
                    <input type="checkbox" checked={tenantIds.includes(t.id)} onChange={() => toggleTenant(t.id)} />
                    {t.name}
                  </label>
                ))}
              </div>
            )}
            {submitted && errors.tenants && (
              <p role="alert" className="text-xs text-danger">
                {errors.tenants}
              </p>
            )}
          </div>
        )}

        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
