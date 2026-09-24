import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateUser, useTenants, useUpdateUser, useUserAvatar } from '@/core/admin/hooks'
import type { UserRecord } from '@/core/admin/types'
import { useAdminApi } from '@/core/admin/useAdminApi'
import { ROLE_META } from '@/core/auth/permissions'
import type { Role } from '@/core/auth/types'
import { describeError } from '@/core/http/describeError'
import { cleanLinks, profileFieldsErrors, type ProfileFieldsValue } from '@/lib/profile'
import { AvatarField } from '@/features/profile/AvatarField'
import { ProfileFieldsInputs } from '@/features/profile/ProfileFieldsInputs'

/** Roles managed from this screen; `client` is created from Tenants. */
const ASSIGNABLE_ROLES: Role[] = ['admin', 'tenant_manager', 'botmaster', 'consultant']

/** Props for {@link UserDialog}. */
export interface UserDialogProps {
  /** `null` = create a user; a user = edit it. */
  user: UserRecord | null
  onClose: () => void
  onSaved?: () => void
}

const FORM_ID = 'user-form'

/**
 * Create and edit an `admin`/`tenant_manager`/`botmaster`/`consultant` user (admin only).
 * It also edits a tenant's `client` account (from the tenant's screen): then
 * role and tenants are fixed and not shown.
 *
 * No password field: on creation, the user is left `pending` and gets an
 * email to activate and choose their own (see `ProvisionUserUseCase`). The
 * email also can't be edited once created (the backend doesn't allow it).
 * Phone, address, social links and photo are optional; the photo can only be
 * set once the user exists (it's saved on pick, like in "My profile").
 */
export function UserDialog({ user, onClose, onSaved }: UserDialogProps) {
  const { t } = useTranslation()
  const editing = user !== null
  const api = useAdminApi()
  const tenants = useTenants()
  const create = useCreateUser()
  const update = useUpdateUser()
  const avatar = useUserAvatar()
  const [email, setEmail] = useState(user?.email ?? '')
  const [name, setName] = useState(user?.name ?? '')
  const [role, setRole] = useState<Role>(user?.role ?? 'botmaster')
  const [active, setActive] = useState(user ? user.status !== 'disabled' : true)
  const [tenantIds, setTenantIds] = useState<string[]>(user?.tenant_ids ?? [])
  const [profile, setProfile] = useState<ProfileFieldsValue>({
    phone: user?.phone ?? '',
    address: user?.address ?? '',
    social_links: { ...user?.social_links },
  })
  // Tras subir/quitar la foto se muestra el registro que devolvió el servidor.
  const [photoOwner, setPhotoOwner] = useState<UserRecord | null>(user)
  const [submitted, setSubmitted] = useState(false)

  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  // La cuenta cliente va atada a su tenant: ni rol ni tenants se tocan aquí.
  const isClient = user?.role === 'client'
  const needsTenants = !isClient && role !== 'admin'
  const errors = {
    email: editing || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim()) ? '' : t('common.validEmail'),
    name: name.trim() ? '' : t('common.nameRequired'),
    tenants: !needsTenants || tenantIds.length > 0 ? '' : t('users.form.tenantsRequired'),
  }
  const profileInvalid = Object.keys(profileFieldsErrors(profile)).length > 0

  function toggleTenant(id: string) {
    setTenantIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))
  }

  async function changePhoto(image: Blob | null) {
    if (!user) return
    try {
      setPhotoOwner(await avatar.mutateAsync({ id: user.id, image }))
    } catch {
      // El error queda en avatar.error y se muestra junto a la foto.
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (errors.email || errors.name || errors.tenants || profileInvalid) return
    const extra = {
      phone: profile.phone.trim(),
      address: profile.address.trim(),
      social_links: cleanLinks(profile.social_links),
    }
    try {
      if (editing) {
        await update.mutateAsync({
          id: user.id,
          patch: {
            name: name.trim(),
            status: active ? 'active' : 'disabled',
            ...(isClient ? {} : { role, tenant_ids: needsTenants ? tenantIds : [] }),
            ...extra,
          },
        })
      } else {
        await create.mutateAsync({
          email: email.trim(),
          name: name.trim(),
          role,
          tenant_ids: needsTenants ? tenantIds : [],
          // Al crear solo se mandan los opcionales que tienen algo.
          ...(extra.phone ? { phone: extra.phone } : {}),
          ...(extra.address ? { address: extra.address } : {}),
          ...(Object.keys(extra.social_links).length ? { social_links: extra.social_links } : {}),
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
      onClose={pending || avatar.isPending ? () => {} : onClose}
      title={isClient ? t('tenants.clientAccount.editTitle') : editing ? t('users.form.editTitle') : t('users.new')}
      description={editing ? user.email : t('users.form.createDescription')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : editing ? t('common.saveChanges') : t('users.form.create')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        {editing && photoOwner && (
          <AvatarField
            name={photoOwner.name}
            src={api.userAvatarUrl(photoOwner)}
            pending={avatar.isPending}
            error={avatar.error ? describeError(avatar.error) : null}
            onPick={(image) => void changePhoto(image)}
            onRemove={() => void changePhoto(null)}
          />
        )}
        {editing ? (
          <Field label={t('users.form.email')}>
            <Input value={user.email} disabled />
          </Field>
        ) : (
          <Field label={t('users.form.email')} error={submitted ? errors.email : undefined}>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="persona@flowsdone.com" autoComplete="off" />
          </Field>
        )}
        <Field label={t('common.name')} error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('profile.fields.fullName')} />
        </Field>
        {!isClient && (
          <Field label={t('profile.fields.role')}>
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ASSIGNABLE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_META[r].label}
                </option>
              ))}
            </Select>
          </Field>
        )}
        {editing && (
          <Field label={t('common.status')}>
            <Select value={active ? 'active' : 'disabled'} onChange={(e) => setActive(e.target.value === 'active')}>
              <option value="active">{t('common.active')}</option>
              <option value="disabled">{t('users.status.disabled')}</option>
            </Select>
          </Field>
        )}
        {needsTenants && (
          <div className="space-y-1.5">
            <span className="text-sm font-medium">{t('nav.tenants')}</span>
            {tenants.isPending ? (
              <Spinner label={t('tenants.loading')} />
            ) : (
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-border p-2">
                {(tenants.data ?? []).map((tenant) => (
                  <label key={tenant.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-muted">
                    <input type="checkbox" checked={tenantIds.includes(tenant.id)} onChange={() => toggleTenant(tenant.id)} />
                    {tenant.name}
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
        <div className="space-y-5 border-t border-border pt-5">
          <div>
            <h3 className="text-sm font-semibold">{t('users.form.profileTitle')}</h3>
            <p className="mt-0.5 text-xs text-muted">{editing ? t('users.form.profileHint') : t('users.form.profileHintCreate')}</p>
          </div>
          <ProfileFieldsInputs value={profile} onChange={setProfile} showErrors={submitted} />
        </div>
        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
