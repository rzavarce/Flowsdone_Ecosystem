import { Pencil, Receipt } from 'lucide-react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useTenantBilling } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import { BillingProfileDialog } from './BillingProfileDialog'

/** Props for {@link BillingProfileCard}. */
export interface BillingProfileCardProps {
  tenantId: string
  tenantName: string
}

/** A single profile field, or nothing if it's empty. */
function Row({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-sm">
      <span className="text-muted">{label}</span>
      <span className="truncate text-right font-medium">{value}</span>
    </div>
  )
}

/**
 * Summary of the selected tenant's billing profile, with editing
 * (admin/tenant_manager - see POLICY["tenant_billing"] in the gateway). A
 * `client` sees this same data, read-only, in "My company"
 * (`features/company/CompanyPage.tsx`).
 */
export function BillingProfileCard({ tenantId, tenantName }: BillingProfileCardProps) {
  const billing = useTenantBilling(tenantId)
  const [editing, setEditing] = useState(false)

  const address = billing.data
    ? [billing.data.city, billing.data.state_province, billing.data.country].filter(Boolean).join(', ')
    : null

  return (
    <Card>
      <CardHeader
        title="Datos de facturación"
        description="Para poder facturar a este tenant."
        action={
          <Button size="sm" variant="secondary" onClick={() => setEditing(true)} disabled={billing.isPending}>
            <Pencil className="size-4" aria-hidden="true" />
            Editar
          </Button>
        }
      />
      <div className="p-5 pt-4">
        {billing.isPending ? (
          <Spinner label="Cargando datos de facturación" />
        ) : billing.isError ? (
          <Alert tone="danger">{describeError(billing.error)}</Alert>
        ) : !billing.data?.legal_name && !billing.data?.tax_id && !billing.data?.billing_email ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <Receipt className="size-4 shrink-0" aria-hidden="true" />
            Todavía no se cargaron los datos de facturación de este tenant.
          </p>
        ) : (
          <div className="divide-y divide-border">
            <Row label="Razón social" value={billing.data.legal_name} />
            <Row label="Identificación fiscal" value={billing.data.tax_id} />
            <Row label="Email de facturación" value={billing.data.billing_email} />
            <Row label="Contacto" value={billing.data.billing_contact_name} />
            <Row label="Dirección" value={address || null} />
            <Row label="Plan" value={billing.data.plan} />
            <Row label="Moneda" value={billing.data.currency} />
          </div>
        )}
      </div>
      {editing && billing.data && (
        <BillingProfileDialog
          tenantId={tenantId}
          tenantName={tenantName}
          profile={billing.data}
          onClose={() => setEditing(false)}
        />
      )}
    </Card>
  )
}
