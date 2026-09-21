import { TrendingDown, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { formatDelta } from '@/lib/format'
import type { Stat } from '@/mocks/data'

/** Tarjeta KPI: valor grande y tendencia frente al periodo anterior. */
export function StatCard({ stat }: { stat: Stat }) {
  const up = stat.delta >= 0
  const Trend = up ? TrendingUp : TrendingDown
  return (
    <Card className="p-4 sm:p-5">
      <p className="text-sm text-muted">{stat.label}</p>
      <p className="mt-2 font-display text-2xl font-bold sm:text-3xl tracking-tight">{stat.value}</p>
      <Badge tone={up ? 'success' : 'danger'} className="mt-3">
        <Trend className="size-3.5" aria-hidden="true" />
        {formatDelta(stat.delta)}
        <span className="sr-only"> frente a la semana anterior</span>
      </Badge>
    </Card>
  )
}
