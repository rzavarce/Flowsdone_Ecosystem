import { ActivityChart } from '@/components/charts/ActivityChart'
import { StatCard } from '@/components/charts/StatCard'
import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { ACTIVITY, STATS } from '@/mocks/data'

/** IDs of the stats the client role sees (a read-only subset). */
const CLIENT_STAT_IDS = ['conversations', 'resolution']

/** Read-only panel for the client role: stats and activity of their organization. */
export function ClientPanel() {
  const { current } = useTenant()
  return (
    <>
      <PageHeader
        title="Mi panel"
        description={current ? `Resultados de ${current.name}.` : 'Resultados de tu organización.'}
      />
      <div className="space-y-6">
        <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 sm:gap-4">
          {STATS.filter((s) => CLIENT_STAT_IDS.includes(s.id)).map((stat) => (
            <StatCard key={stat.id} stat={stat} />
          ))}
        </section>
        <ActivityChart data={ACTIVITY} />
      </div>
    </>
  )
}
