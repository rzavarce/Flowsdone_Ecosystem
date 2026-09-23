import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useUpdateTenantBilling } from '@/core/admin/hooks'
import type { TenantBillingProfile } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'

/** Props for {@link BillingProfileDialog}. */
export interface BillingProfileDialogProps {
  tenantId: string
  tenantName: string
  /** Current profile (any field may come back `null`: it's filled in gradually). */
  profile: TenantBillingProfile
  onClose: () => void
}

const FORM_ID = 'billing-profile-form'

/** Text -> `null` if left empty, so empty strings never get persisted. */
const orNull = (v: string) => (v.trim() ? v.trim() : null)

/**
 * A tenant's billing data (admin/tenant_manager). Pure data capture for
 * invoicing purposes - there's no billing engine or real plan/pricing behind
 * it; `plan`/`billing_cycle` are free text.
 */
export function BillingProfileDialog({ tenantId, tenantName, profile, onClose }: BillingProfileDialogProps) {
  const update = useUpdateTenantBilling()
  const [fields, setFields] = useState({
    legal_name: profile.legal_name ?? '',
    tax_id: profile.tax_id ?? '',
    billing_email: profile.billing_email ?? '',
    billing_contact_name: profile.billing_contact_name ?? '',
    billing_phone: profile.billing_phone ?? '',
    address_line1: profile.address_line1 ?? '',
    address_line2: profile.address_line2 ?? '',
    city: profile.city ?? '',
    state_province: profile.state_province ?? '',
    postal_code: profile.postal_code ?? '',
    country: profile.country ?? '',
    currency: profile.currency ?? '',
    plan: profile.plan ?? '',
    billing_cycle: profile.billing_cycle ?? '',
    notes: profile.notes ?? '',
  })

  const set = (key: keyof typeof fields) => (e: ChangeEvent<HTMLInputElement>) =>
    setFields((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await update.mutateAsync({
        tenantId,
        patch: Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, orNull(v)])),
      })
      onClose()
    } catch {
      // El error queda en update.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={update.isPending ? () => {} : onClose}
      title="Datos de facturación"
      description={tenantName}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={update.isPending}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={update.isPending}>
            {update.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Razón social">
            <Input value={fields.legal_name} onChange={set('legal_name')} placeholder="Acme Corp S.A. de C.V." />
          </Field>
          <Field label="Identificación fiscal" hint="RFC, NIF, VAT, EIN…">
            <Input value={fields.tax_id} onChange={set('tax_id')} />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Email de facturación">
            <Input type="email" value={fields.billing_email} onChange={set('billing_email')} />
          </Field>
          <Field label="Contacto de facturación">
            <Input value={fields.billing_contact_name} onChange={set('billing_contact_name')} />
          </Field>
        </div>
        <Field label="Teléfono">
          <Input type="tel" value={fields.billing_phone} onChange={set('billing_phone')} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Dirección">
            <Input value={fields.address_line1} onChange={set('address_line1')} placeholder="Calle y número" />
          </Field>
          <Field label="Dirección (línea 2)">
            <Input value={fields.address_line2} onChange={set('address_line2')} placeholder="Piso, oficina…" />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Ciudad">
            <Input value={fields.city} onChange={set('city')} />
          </Field>
          <Field label="Estado/provincia">
            <Input value={fields.state_province} onChange={set('state_province')} />
          </Field>
          <Field label="Código postal">
            <Input value={fields.postal_code} onChange={set('postal_code')} />
          </Field>
        </div>
        <Field label="País">
          <Input value={fields.country} onChange={set('country')} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Moneda" hint="USD, MXN…">
            <Input value={fields.currency} onChange={set('currency')} />
          </Field>
          <Field label="Plan">
            <Input value={fields.plan} onChange={set('plan')} placeholder="starter, pro…" />
          </Field>
          <Field label="Ciclo de facturación">
            <Input value={fields.billing_cycle} onChange={set('billing_cycle')} placeholder="mensual, anual…" />
          </Field>
        </div>

        <Field label="Notas">
          <Input value={fields.notes} onChange={set('notes')} />
        </Field>

        {update.error && <Alert tone="danger">{describeError(update.error)}</Alert>}
      </form>
    </Dialog>
  )
}
