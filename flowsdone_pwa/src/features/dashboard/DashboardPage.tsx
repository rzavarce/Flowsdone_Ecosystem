import { PageHeader } from '@/components/layout/PageHeader'
import { ACTIVITY, RECENT_CONVERSATIONS, STATS } from '@/mocks/data'
import { ActivityChart } from '@/components/charts/ActivityChart'
import { RecentConversations } from './RecentConversations'
import { StatCard } from '@/components/charts/StatCard'

/** Overview screen: KPIs, weekly activity and recent conversations. */
export function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Resumen de la actividad de tu plataforma." />
      <div className="space-y-6">
        <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          {STATS.map((stat) => (
            <StatCard key={stat.id} stat={stat} />
          ))}
        </section>
        <div className="grid gap-6 xl:grid-cols-5">
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
