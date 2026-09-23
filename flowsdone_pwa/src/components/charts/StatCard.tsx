import { BarChart3, Bot, MessageSquare, MessagesSquare, Timer, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { formatDelta } from '@/lib/format'
import type { Stat } from '@/mocks/data'
import { useTranslation } from 'react-i18next'

/** Icon per stat id; unknown ids fall back to a generic chart icon. */
const STAT_ICONS: Record<string, LucideIcon> = {
  conversations: MessageSquare,
  messages: MessagesSquare,
  response: Timer,
  resolution: Bot,
}

/** KPI card (TailAdmin "metric" style): icon tile, label, large value and trend against the previous period. */
export function StatCard({ stat }: { stat: Stat }) {
  const { t } = useTranslation()
  const up = stat.delta >= 0
  const Trend = up ? TrendingUp : TrendingDown
  const Icon = STAT_ICONS[stat.id] ?? BarChart3
  return (
    <Card className="p-4 sm:p-5 md:p-6">
      <span className="flex size-12 items-center justify-center rounded-xl bg-surface-muted">
        <Icon className="size-6 text-foreground/85" strokeWidth={1.75} aria-hidden="true" />
      </span>
      <div className="mt-5 flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm text-muted">{stat.label}</p>
          <p className="mt-2 font-display text-2xl font-bold sm:text-3xl">{stat.value}</p>
        </div>
        <Badge tone={up ? 'success' : 'danger'}>
          <Trend className="size-3.5" aria-hidden="true" />
          {formatDelta(stat.delta)}
          <span className="sr-only"> {t('dashboard.vsLastWeek')}</span>
        </Badge>
      </div>
    </Card>
  )
}
