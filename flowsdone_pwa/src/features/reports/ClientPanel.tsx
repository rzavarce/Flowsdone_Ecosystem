import { ActivityChart } from '@/components/charts/ActivityChart'
import { StatCard } from '@/components/charts/StatCard'
import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { ACTIVITY, STATS } from '@/mocks/data'
import { useTranslation } from 'react-i18next'

/** IDs of the stats the client role sees (a read-only subset). */
const CLIENT_STAT_IDS = ['conversations', 'resolution']

/** Read-only panel for the client role: stats and activity of their organization. */
export function ClientPanel() {
  const { t } = useTranslation()
  const { current } = useTenant()
  return (
    <>
      <PageHeader
        title={t('reports.clientTitle')}
        description={current ? t('reports.resultsOf', { name: current.name }) : t('reports.resultsOwn')}
      />
      <div className="space-y-6">
        <section aria-label={t('dashboard.indicators')} className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6">
          {STATS.filter((s) => CLIENT_STAT_IDS.includes(s.id)).map((stat) => (
            <StatCard key={stat.id} stat={stat} />
          ))}
        </section>
        <ActivityChart data={ACTIVITY} />
      </div>
    </>
  )
}
