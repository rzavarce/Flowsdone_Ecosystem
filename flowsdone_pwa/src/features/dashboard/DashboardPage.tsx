import { PageHeader } from '@/components/layout/PageHeader'
import { ACTIVITY, RECENT_CONVERSATIONS, STATS } from '@/mocks/data'
import { ActivityChart } from '@/components/charts/ActivityChart'
import { RecentConversations } from './RecentConversations'
import { StatCard } from '@/components/charts/StatCard'
import { useTranslation } from 'react-i18next'

/** Overview screen: KPIs, weekly activity and recent conversations. */
export function DashboardPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('nav.dashboard')} description={t('dashboard.description')} />
      <div className="space-y-4 md:space-y-6">
        <section aria-label={t('dashboard.indicators')} className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:gap-6 xl:grid-cols-4">
          {STATS.map((stat) => (
            <StatCard key={stat.id} stat={stat} />
          ))}
        </section>
        <div className="grid gap-4 md:gap-6 xl:grid-cols-5">
          <div className="min-w-0 xl:col-span-3">
            <ActivityChart data={ACTIVITY} className="h-full" />
          </div>
          <div className="min-w-0 xl:col-span-2">
            <RecentConversations items={RECENT_CONVERSATIONS} className="h-full" />
          </div>
        </div>
      </div>
    </>
  )
}
