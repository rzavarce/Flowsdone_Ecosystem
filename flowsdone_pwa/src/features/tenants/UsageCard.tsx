import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Card, CardHeader } from '@/components/ui/Card'
import { Select } from '@/components/ui/Field'
import { Spinner } from '@/components/ui/Spinner'
import { useStatement } from '@/core/admin/billingHooks'
import { describeError } from '@/core/http/describeError'
import { StatementView } from '@/features/billing/StatementView'
import { currentPeriod, formatPeriod, recentPeriods } from '@/lib/money'
import { useTranslation } from 'react-i18next'

/** Months offered in the period selector (current + 5 previous). */
const PERIODS = 6

/**
 * The tenant's usage and charges for a month (current by default): messages
 * per channel against the plan, overage and total. Admins also get
 * Flowsdone's cost and margin (the gateway strips them for managers).
 */
export function UsageCard({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation()
  const [period, setPeriod] = useState(currentPeriod())
  const statement = useStatement(tenantId, period)

  return (
    <Card>
      <CardHeader
        title={t('usage.title')}
        description={t('usage.description')}
        action={
          <Select aria-label={t('usage.period')} value={period} onChange={(e) => setPeriod(e.target.value)} className="h-9 w-auto">
            {recentPeriods(PERIODS).map((p) => (
              <option key={p} value={p}>
                {formatPeriod(p)}
              </option>
            ))}
          </Select>
        }
      />
      <div className="p-5 pt-4 sm:px-6">
        {statement.isPending ? (
          <Spinner label={t('usage.loading')} />
        ) : statement.isError ? (
          <Alert tone="danger">{describeError(statement.error)}</Alert>
        ) : (
          <StatementView statement={statement.data} />
        )}
      </div>
    </Card>
  )
}
