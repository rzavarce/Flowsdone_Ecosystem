import { Building2 } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useCompany } from '@/core/company/useCompany'
import { describeError } from '@/core/http/describeError'

/** A single company field, or nothing if it's empty. */
function Row({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2.5 text-sm last:border-0">
      <span className="text-muted">{label}</span>
      <span className="text-right font-medium">{value}</span>
    </div>
  )
}

/**
 * "My company": the own tenant's billing data, read-only (`client`). It's
 * edited by an admin/tenant_manager from Tenants (`BillingProfileCard`);
 * this screen never goes through the admin API, it uses `GET /me/billing-profile`.
 */
export function CompanyPage() {
  const company = useCompany()
  const address = company.data
    ? [company.data.address_line1, company.data.address_line2, company.data.city, company.data.state_province, company.data.country]
        .filter(Boolean)
        .join(', ')
    : null

  return (
    <>
      <PageHeader title="Mi empresa" description="Los datos de facturación de tu organización." />
      {company.isPending ? (
        <Spinner label="Cargando los datos de tu empresa" className="py-20" />
      ) : company.isError ? (
        <Alert tone="danger">{describeError(company.error)}</Alert>
      ) : !company.data ? (
        <EmptyState
          icon={Building2}
          title="Todavía no hay datos cargados"
          description="Pídele a tu administrador que complete los datos de facturación de tu empresa."
        />
      ) : (
        <Card className="max-w-xl p-5">
          <Row label="Razón social" value={company.data.legal_name} />
          <Row label="Identificación fiscal" value={company.data.tax_id} />
          <Row label="Email de facturación" value={company.data.billing_email} />
          <Row label="Contacto de facturación" value={company.data.billing_contact_name} />
          <Row label="Teléfono" value={company.data.billing_phone} />
          <Row label="Dirección" value={address || null} />
          <Row label="Código postal" value={company.data.postal_code} />
          <Row label="Plan" value={company.data.plan} />
          <Row label="Ciclo de facturación" value={company.data.billing_cycle} />
          <Row label="Moneda" value={company.data.currency} />
        </Card>
      )}
    </>
  )
}
