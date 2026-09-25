import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Spinner } from '@/components/ui/Spinner'
import type { ReportKey } from '@/core/analytics/analyticsApi'
import { useReports } from '@/core/analytics/useDashboard'
import { describeError } from '@/core/http/describeError'
import { useTenant } from '@/core/tenant/useTenant'
import { AnalyticsDashboard } from '@/features/dashboard/AnalyticsDashboard'
import { cn } from '@/lib/cn'

/**
 * Reports section: one Metabase dashboard per tab (channels, agents,
 * contacts, hours, usage), for the tenant chosen in the top bar. The open
 * tab lives in the URL (`?r=`) so a report can be linked.
 */
export function ReportsPage() {
  const { t } = useTranslation()
  const { current } = useTenant()
  const reports = useReports()
  const [params, setParams] = useSearchParams()
  const available = reports.data ?? []
  const requested = params.get('r') as ReportKey | null
  const active = requested && available.includes(requested) ? requested : available[0]

  return (
    <>
      <PageHeader
        title={t('reports.title')}
        description={current ? t('reports.descriptionTenant', { name: current.name }) : t('reports.description')}
      />
      {reports.isPending ? (
        <Spinner label={t('dashboard.analytics.loading')} className="py-24" />
      ) : reports.isError ? (
        <Alert tone="danger">{describeError(reports.error)}</Alert>
      ) : !active ? (
        <Alert tone="info">{t('reports.none')}</Alert>
      ) : (
        <div className="space-y-4">
          <div role="tablist" aria-label={t('reports.title')} className="flex flex-wrap gap-1 rounded-xl bg-surface-muted p-1 sm:inline-flex">
            {available.map((key) => (
              <button
                key={key}
                role="tab"
                type="button"
                aria-selected={key === active}
                onClick={() => setParams({ r: key }, { replace: true })}
                className={cn(
                  'cursor-pointer rounded-lg px-4 py-1.5 text-sm font-medium transition',
                  key === active ? 'bg-surface text-foreground shadow-theme-xs' : 'text-muted hover:text-foreground',
                )}
              >
                {t(`reports.tabs.${key}`)}
              </button>
            ))}
          </div>
          <AnalyticsDashboard key={active} title={t(`reports.tabs.${active}`)} report={active} />
        </div>
      )}
    </>
  )
}
