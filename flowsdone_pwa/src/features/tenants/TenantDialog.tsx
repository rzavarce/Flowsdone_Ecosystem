import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateTenant, useUpdateTenant } from '@/core/admin/hooks'
import type { TenantRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'
import { useTranslation } from 'react-i18next'

/** Props for {@link TenantDialog}. */
export interface TenantDialogProps {
  /** `null` = create a tenant; a tenant = edit it. */
  tenant: TenantRecord | null
  onClose: () => void
  /** Called with the created tenant (to select it). */
  onSaved?: (tenant: TenantRecord) => void
}

const FORM_ID = 'tenant-form'

/** Create and edit a tenant (admin only). The slug is derived from the name until it's touched. */
export function TenantDialog({ tenant, onClose, onSaved }: TenantDialogProps) {
  const { t } = useTranslation()
  const editing = tenant !== null
  const create = useCreateTenant()
  const update = useUpdateTenant()
  const [name, setName] = useState(tenant?.name ?? '')
  const [slug, setSlug] = useState(tenant?.slug ?? '')
  const [slugTouched, setSlugTouched] = useState(editing)
  const [clientEmail, setClientEmail] = useState('')
  const [clientName, setClientName] = useState('')
  const [submitted, setSubmitted] = useState(false)

  const effectiveSlug = slugTouched ? slug : slugify(name)
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  const errors = {
    name: name.trim() ? '' : t('common.nameRequired'),
    slug: effectiveSlug ? '' : t('common.slugRequired'),
    // Solo al crear: al editar no se toca el usuario `client` del tenant.
    clientEmail: editing || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(clientEmail.trim()) ? '' : t('common.validEmail'),
    clientName: editing || clientName.trim() ? '' : t('tenants.form.clientNameRequired'),
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (errors.name || errors.slug || errors.clientEmail || errors.clientName) return
    try {
      const saved = editing
        ? await update.mutateAsync({ id: tenant.id, patch: { name: name.trim(), slug: effectiveSlug } })
        : await create.mutateAsync({
            name: name.trim(),
            slug: effectiveSlug,
            client_email: clientEmail.trim(),
            client_name: clientName.trim(),
          })
      onSaved?.(saved)
      onClose()
    } catch {
      // El error queda en create.error / update.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={editing ? t('tenants.form.editTitle') : t('tenants.new')}
      description={editing ? tenant.name : t('tenants.form.createDescription')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : editing ? t('common.saveChanges') : t('tenants.form.create')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label={t('common.name')} error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Clínica Vital" />
        </Field>
        <Field
          label={t('common.slug')}
          hint={editing ? t('tenants.form.slugEditHint') : t('tenants.form.slugHint')}
          error={submitted ? errors.slug : undefined}
        >
          <Input
            value={effectiveSlug}
            onChange={(e) => {
              setSlugTouched(true)
              setSlug(slugify(e.target.value))
            }}
            placeholder="clinica-vital"
            autoComplete="off"
          />
        </Field>
        {!editing && (
          <>
            <Field label={t('tenants.form.clientEmail')} hint={t('tenants.form.clientEmailHint')} error={submitted ? errors.clientEmail : undefined}>
              <Input
                type="email"
                value={clientEmail}
                onChange={(e) => setClientEmail(e.target.value)}
                placeholder="cliente@empresa.com"
                autoComplete="off"
              />
            </Field>
            <Field label={t('tenants.form.clientName')} error={submitted ? errors.clientName : undefined}>
              <Input value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder={t('tenants.form.clientNamePlaceholder')} />
            </Field>
          </>
        )}
        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
