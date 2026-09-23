import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateTenant, useTenantBilling, useTenants, useUpdateTenantBilling } from '@/core/admin/hooks'
import type { TenantBillingProfile } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'
import { StepFrame } from './StepFrame'
import { useTranslation } from 'react-i18next'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const BILLING_FIELDS = [
  'legal_name', 'tax_id', 'billing_email', 'billing_contact_name', 'billing_phone',
  'address_line1', 'city', 'postal_code', 'country',
] as const
type BillingField = (typeof BILLING_FIELDS)[number]

/** Billing form values from a stored profile (or empty). */
const billingValues = (profile?: TenantBillingProfile) =>
  Object.fromEntries(BILLING_FIELDS.map((f) => [f, profile?.[f] ?? ''])) as Record<BillingField, string>

/**
 * Step 1: the company. New client: tenant (name, slug), its client account
 * (gets the activation email) and billing data. Resumed client: only its
 * billing data, prefilled. The billing email is required (usage alerts).
 */
export function CompanyStep({ tenantId, onDone }: { tenantId?: string; onDone: (tenantId: string) => void }) {
  const { t } = useTranslation()
  const tenants = useTenants()
  const billing = useTenantBilling(tenantId)
  if (tenantId && (billing.isPending || tenants.isPending)) return <Spinner label={t('onboarding.loading')} className="py-16" />
  return (
    <CompanyForm
      key={tenantId ?? 'new'}
      tenantId={tenantId}
      tenantName={tenants.data?.find((x) => x.id === tenantId)?.name}
      profile={billing.data}
      onDone={onDone}
    />
  )
}

function CompanyForm({
  tenantId,
  tenantName,
  profile,
  onDone,
}: {
  tenantId?: string
  tenantName?: string
  profile?: TenantBillingProfile
  onDone: (tenantId: string) => void
}) {
  const { t } = useTranslation()
  const create = useCreateTenant()
  const update = useUpdateTenantBilling()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [clientName, setClientName] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  const [fields, setFields] = useState(() => billingValues(profile))
  const [submitted, setSubmitted] = useState(false)
  const effectiveSlug = slugTouched ? slug : slugify(name)
  const isNew = !tenantId

  const errors = {
    name: isNew && !name.trim() ? t('common.nameRequired') : undefined,
    slug: isNew && !effectiveSlug ? t('common.slugRequired') : undefined,
    clientName: isNew && !clientName.trim() ? t('common.fieldRequired', { field: t('common.name') }) : undefined,
    clientEmail: isNew && !EMAIL.test(clientEmail.trim()) ? t('common.validEmail') : undefined,
    billing_email: !EMAIL.test(fields.billing_email.trim()) ? t('common.validEmail') : undefined,
  }
  const shown = (key: keyof typeof errors) => (submitted ? errors[key] : undefined)
  const set = (key: BillingField) => (e: ChangeEvent<HTMLInputElement>) => setFields((f) => ({ ...f, [key]: e.target.value }))
  const pending = create.isPending || update.isPending

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (Object.values(errors).some(Boolean)) return
    try {
      const id =
        tenantId ??
        (await create.mutateAsync({ name: name.trim(), slug: effectiveSlug, client_email: clientEmail.trim(), client_name: clientName.trim() })).id
      await update.mutateAsync({
        tenantId: id,
        patch: { ...Object.fromEntries(BILLING_FIELDS.map((f) => [f, fields[f].trim() || null])), currency: profile?.currency ?? 'EUR' },
      })
      onDone(id)
    } catch {
      // El error queda en la mutación y se muestra abajo.
    }
  }

  const error = create.error ?? update.error
  return (
    <StepFrame
      title={t('onboarding.steps.company')}
      description={isNew ? t('onboarding.company.description') : t('onboarding.company.existing')}
      onSubmit={submit}
      pending={pending}
      error={error ? describeError(error) : null}
    >
      {isNew ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Field label={t('common.name')} error={shown('name')}>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label={t('common.slug')} hint={t('common.slugHint')} error={shown('slug')}>
              <Input
                value={effectiveSlug}
                onChange={(e) => {
                  setSlug(e.target.value)
                  setSlugTouched(true)
                }}
                className="font-mono"
              />
            </Field>
          </div>
          <fieldset className="space-y-3">
            <legend className="text-sm font-semibold">{t('onboarding.company.account')}</legend>
            <p className="text-xs text-muted">{t('onboarding.company.accountHint')}</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <Field label={t('onboarding.company.clientName')} error={shown('clientName')}>
                <Input value={clientName} onChange={(e) => setClientName(e.target.value)} />
              </Field>
              <Field label={t('onboarding.company.clientEmail')} error={shown('clientEmail')}>
                <Input type="email" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} />
              </Field>
            </div>
          </fieldset>
        </div>
      ) : (
        <p className="text-base font-medium">{tenantName}</p>
      )}

      <fieldset className="space-y-4">
        <legend className="text-sm font-semibold">{t('onboarding.company.billing')}</legend>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Field label={t('billing.fields.legal_name')}>
            <Input value={fields.legal_name} onChange={set('legal_name')} />
          </Field>
          <Field label={t('billing.fields.tax_id')} hint={t('billing.hints.tax_id')}>
            <Input value={fields.tax_id} onChange={set('tax_id')} />
          </Field>
          <Field label={t('billing.fields.billing_email')} hint={t('onboarding.company.billingEmailHint')} error={shown('billing_email')}>
            <Input type="email" value={fields.billing_email} onChange={set('billing_email')} />
          </Field>
          <Field label={t('billing.fields.billing_contact_name')}>
            <Input value={fields.billing_contact_name} onChange={set('billing_contact_name')} />
          </Field>
          <Field label={t('billing.fields.billing_phone')}>
            <Input type="tel" value={fields.billing_phone} onChange={set('billing_phone')} />
          </Field>
          <Field label={t('billing.fields.address_line1')}>
            <Input value={fields.address_line1} onChange={set('address_line1')} />
          </Field>
          <Field label={t('billing.fields.city')}>
            <Input value={fields.city} onChange={set('city')} />
          </Field>
          <Field label={t('billing.fields.postal_code')}>
            <Input value={fields.postal_code} onChange={set('postal_code')} />
          </Field>
          <Field label={t('billing.fields.country')}>
            <Input value={fields.country} onChange={set('country')} />
          </Field>
        </div>
      </fieldset>
    </StepFrame>
  )
}
