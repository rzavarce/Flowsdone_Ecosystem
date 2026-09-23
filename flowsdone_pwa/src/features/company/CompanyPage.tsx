import { Building2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Field'
import { Spinner } from '@/components/ui/Spinner'
import { useCompany, useMyUsage } from '@/core/company/useCompany'
import { describeError } from '@/core/http/describeError'
import { StatementView } from '@/features/billing/StatementView'
import { currentPeriod, formatPeriod, recentPeriods } from '@/lib/money'
import { useTranslation } from 'react-i18next'

/** The own tenant's usage and charges per month (never Flowsdone's costs). */
function MyUsageCard() {
  const { t } = useTranslation()
  const [period, setPeriod] = useState(currentPeriod())
  const usage = useMyUsage(period)
  if (usage.data === null) return null
  return (
    <Card className="max-w-xl">
      <CardHeader
        title={t('usage.title')}
        description={t('usage.description')}
        action={
          <Select aria-label={t('usage.period')} value={period} onChange={(e) => setPeriod(e.target.value)} className="h-9 w-auto">
            {recentPeriods(6).map((p) => (
              <option key={p} value={p}>
                {formatPeriod(p)}
              </option>
            ))}
          </Select>
        }
      />
      <div className="p-5 pt-4">
        {usage.isPending ? (
          <Spinner label={t('usage.loading')} />
        ) : usage.isError ? (
          <Alert tone="danger">{describeError(usage.error)}</Alert>
        ) : (
          <StatementView statement={usage.data} />
        )}
      </div>
    </Card>
  )
}

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
 * "My company": the own tenant's billing data and monthly usage, read-only
 * (`client`). Usage comes from `GET /me/usage`. The billing data is
 * edited by an admin/tenant_manager from Tenants (`BillingProfileCard`);
 * this screen never goes through the admin API, it uses `GET /me/billing-profile`.
 */
export function CompanyPage() {
  const { t } = useTranslation()
  const company = useCompany()
  const address = company.data
    ? [company.data.address_line1, company.data.address_line2, company.data.city, company.data.state_province, company.data.country]
        .filter(Boolean)
        .join(', ')
    : null

  return (
    <>
      <PageHeader title={t('nav.company')} description={t('company.description')} />
      {company.isPending ? (
        <Spinner label={t('company.loading')} className="py-20" />
      ) : company.isError ? (
        <Alert tone="danger">{describeError(company.error)}</Alert>
      ) : !company.data ? (
        <EmptyState
          icon={Building2}
          title={t('company.empty.title')}
          description={t('company.empty.description')}
        />
      ) : (
        <Card className="mb-6 max-w-xl p-5">
          <Row label={t('billing.fields.legal_name')} value={company.data.legal_name} />
          <Row label={t('billing.fields.tax_id')} value={company.data.tax_id} />
          <Row label={t('billing.fields.billing_email')} value={company.data.billing_email} />
          <Row label={t('billing.fields.billing_contact_name')} value={company.data.billing_contact_name} />
          <Row label={t('billing.fields.billing_phone')} value={company.data.billing_phone} />
          <Row label={t('billing.fields.address_line1')} value={address || null} />
          <Row label={t('billing.fields.postal_code')} value={company.data.postal_code} />
          <Row label={t('billing.fields.plan')} value={company.data.plan} />
          <Row label={t('billing.fields.billing_cycle')} value={company.data.billing_cycle} />
          <Row label={t('billing.fields.currency')} value={company.data.currency} />
        </Card>
      )}
      <MyUsageCard />
    </>
  )
}
