import { AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import type { Statement } from '@/core/admin/types'
import { cn } from '@/lib/cn'
import { formatMoney, formatNumber } from '@/lib/money'
import { channelLabel } from './labels'
import { useTranslation } from 'react-i18next'

/** A label/amount row of the statement totals. */
function Total({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4 py-1.5 text-sm', strong && 'text-base font-semibold')}>
      <span className={strong ? undefined : 'text-muted'}>{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  )
}

/** Props for {@link StatementView}. */
export interface StatementViewProps {
  statement: Statement
}

/**
 * A month's usage and charges: one progress bar per channel (agent-handled
 * messages against the plan's included ones), the month's total and, when
 * the backend sends them (admins only), Flowsdone's cost and margin, token
 * use and warnings (fair use, models outside the plan, meters without rate).
 * Shared by the Tenants screen and "My company".
 */
export function StatementView({ statement: s }: StatementViewProps) {
  const { t } = useTranslation()
  const money = (micros: number | null) => formatMoney(micros, s.currency)
  const warnings = [
    s.over_token_allowance && t('usage.overTokens', { allowance: formatNumber(s.token_allowance) }),
    s.disallowed_models.length > 0 && t('usage.disallowedModels', { models: s.disallowed_models.join(', ') }),
    (s.unrated_meters ?? 0) > 0 && t('usage.unrated', { count: s.unrated_meters ?? 0 }),
  ].filter(Boolean) as string[]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone={s.status === 'closed' ? 'neutral' : 'primary'}>{t(`usage.status.${s.status}`)}</Badge>
        <span className="font-medium">{s.plan_name ?? t('usage.noPlan')}</span>
      </div>

      {s.channels.length === 0 ? (
        <p className="text-sm text-muted">{t('usage.empty')}</p>
      ) : (
        <ul className="space-y-4">
          {s.channels.map((c) => {
            const pct = c.included > 0 ? Math.min(100, (100 * c.messages) / c.included) : c.messages > 0 ? 100 : 0
            const over = c.overage_messages > 0
            return (
              <li key={c.channel_type}>
                <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                  <span className="font-medium">{channelLabel(c.channel_type)}</span>
                  <span className="text-muted tabular-nums">
                    {c.included > 0
                      ? t('usage.of', { used: formatNumber(c.messages), included: formatNumber(c.included) })
                      : `${formatNumber(c.messages)} · ${t('usage.unlimited')}`}
                  </span>
                </div>
                <div
                  className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-muted"
                  role="progressbar"
                  aria-label={channelLabel(c.channel_type)}
                  aria-valuemin={0}
                  aria-valuemax={Math.max(c.included, c.messages)}
                  aria-valuenow={c.messages}
                >
                  <div className={cn('h-full rounded-full', over ? 'bg-warning' : 'bg-primary')} style={{ width: `${pct}%` }} />
                </div>
                {over && (
                  <p className="mt-1 text-xs text-warning">
                    {t('usage.overageMessages', { count: c.overage_messages })} · {money(c.overage_amount_micros)}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <div className="divide-y divide-border border-t border-border pt-2">
        <Total label={t('usage.fee')} value={money(s.monthly_fee_micros)} />
        <Total label={t('usage.overageTotal')} value={money(s.overage_amount_micros)} />
        <Total label={s.status === 'closed' ? t('usage.total') : t('usage.totalEstimated')} value={money(s.revenue_micros)} strong />
        {s.cost_micros !== null && <Total label={t('usage.cost')} value={money(s.cost_micros)} />}
        {s.margin_micros !== null && (
          <Total label={t('usage.margin')} value={`${money(s.margin_micros)}${s.margin_pct !== null ? ` · ${s.margin_pct} %` : ''}`} />
        )}
      </div>

      {(s.llm_input_tokens > 0 || s.llm_output_tokens > 0) && (
        <p className="text-xs text-muted">
          {t('usage.tokens', { input: formatNumber(s.llm_input_tokens), output: formatNumber(s.llm_output_tokens) })}
        </p>
      )}
      {warnings.length > 0 && (
        <ul className="space-y-1">
          {warnings.map((w) => (
            <li key={w} className="flex items-start gap-1.5 text-xs text-warning">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
