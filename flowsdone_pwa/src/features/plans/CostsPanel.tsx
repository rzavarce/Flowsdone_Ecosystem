import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Spinner } from '@/components/ui/Spinner'
import { useCostRates, useDeleteCostRate, useUnratedMeters } from '@/core/admin/billingHooks'
import type { CostRate, CostRateInput } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { kindLabel, unitLabel } from '@/features/billing/labels'
import { formatMoney, formatNumber } from '@/lib/money'
import { CostRateDialog } from './CostRateDialog'
import { useTranslation } from 'react-i18next'

/**
 * "Costs" tab (admin): the versioned cost catalog, and the meters used in
 * the last 30 days that no rate covers yet (valued at 0 until one is added,
 * which then also applies to the usage already measured).
 */
export function CostsPanel() {
  const { t } = useTranslation()
  const rates = useCostRates()
  const unrated = useUnratedMeters()
  const remove = useDeleteCostRate()
  const [creating, setCreating] = useState<Partial<CostRateInput> | null>(null)
  const [deleting, setDeleting] = useState<CostRate | null>(null)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title={t('costs.unrated.title')} description={t('costs.unrated.description')} />
        <div className="p-5 pt-4 sm:px-6">
          {unrated.isPending ? (
            <Spinner label={t('costs.rates.loading')} />
          ) : unrated.isError ? (
            <Alert tone="danger">{describeError(unrated.error)}</Alert>
          ) : unrated.data.length === 0 ? (
            <p className="text-sm text-muted">{t('costs.unrated.empty')}</p>
          ) : (
            <ul className="divide-y divide-border">
              {unrated.data.map((m) => (
                <li key={`${m.kind}/${m.provider}/${m.sku}/${m.unit}`} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="min-w-0">
                    <Badge tone="warning">{kindLabel(m.kind)}</Badge>{' '}
                    <span className="font-mono">
                      {m.provider} · {m.sku}
                    </span>{' '}
                    <span className="text-muted">
                      {formatNumber(m.quantity)} {unitLabel(m.unit)}
                    </span>
                  </span>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setCreating({ kind: m.kind as CostRate['kind'], provider: m.provider, sku: m.sku, unit: m.unit })}
                  >
                    <Plus className="size-4" aria-hidden="true" />
                    {t('costs.unrated.add')}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader
          title={t('costs.rates.title')}
          description={t('costs.rates.description')}
          action={
            <Button size="sm" onClick={() => setCreating({})}>
              <Plus className="size-4" aria-hidden="true" />
              {t('costs.rates.new')}
            </Button>
          }
        />
        <div className="p-5 pt-4 sm:px-6">
          {rates.isPending ? (
            <Spinner label={t('costs.rates.loading')} />
          ) : rates.isError ? (
            <Alert tone="danger">{describeError(rates.error)}</Alert>
          ) : rates.data.length === 0 ? (
            <p className="text-sm text-muted">{t('costs.rates.empty')}</p>
          ) : (
            <ul className="divide-y divide-border">
              {rates.data.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="min-w-0">
                    <Badge>{kindLabel(r.kind)}</Badge>{' '}
                    <span className="font-mono">
                      {r.provider} · {r.sku}
                    </span>
                    <span className="block text-xs text-muted">
                      {t('costs.rates.per', {
                        price: formatMoney(r.price_micros, r.currency),
                        quantity: formatNumber(r.per_quantity),
                        unit: unitLabel(r.unit),
                      })}{' '}
                      · {t('costs.rates.validFrom')} {new Date(r.valid_from).toLocaleDateString(currentLocale())}
                      {r.note ? ` · ${r.note}` : ''}
                    </span>
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      remove.reset()
                      setDeleting(r)
                    }}
                    aria-label={t('common.deleteItem', { name: `${r.provider} ${r.sku}` })}
                  >
                    <Trash2 className="size-4" aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>

      {creating && <CostRateDialog initial={creating} onClose={() => setCreating(null)} />}
      <ConfirmDialog
        open={deleting !== null}
        title={t('costs.rates.deleteTitle')}
        description={t('costs.rates.deleteDescription')}
        confirmLabel={t('costs.rates.deleteConfirm')}
        pending={remove.isPending}
        error={remove.error ? describeError(remove.error) : null}
        onCancel={() => setDeleting(null)}
        onConfirm={() =>
          deleting &&
          void remove
            .mutateAsync(deleting.id)
            .then(() => setDeleting(null))
            .catch(() => {})
        }
      />
    </div>
  )
}
