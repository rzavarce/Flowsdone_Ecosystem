import { Pencil, Plus, Receipt, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import { useDeletePlan, usePlans } from '@/core/admin/billingHooks'
import type { Plan } from '@/core/admin/types'
import { ApiError } from '@/core/http/apiFetch'
import { describeError } from '@/core/http/describeError'
import { channelLabel, modeLabel } from '@/features/billing/labels'
import { cn } from '@/lib/cn'
import { formatMoney, formatNumber } from '@/lib/money'
import { CostsPanel } from './CostsPanel'
import { PlanDialog } from './PlanDialog'
import { useTranslation } from 'react-i18next'

type Tab = 'plans' | 'costs'

/** One plan's summary card. */
function PlanCard({ plan, onEdit, onDelete }: { plan: Plan; onEdit: () => void; onDelete: () => void }) {
  const { t } = useTranslation()
  const channels = [...new Set([...Object.keys(plan.included_messages), ...Object.keys(plan.overage_price_micros)])]
  return (
    <Card className={cn('flex flex-col p-5', !plan.active && 'opacity-70')}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <span className="truncate">{plan.name}</span>
            {!plan.active && <Badge tone="warning">{t('plans.inactive')}</Badge>}
          </h2>
          <p className="font-mono text-xs text-muted">{plan.code}</p>
        </div>
        <p className="text-right text-lg font-semibold tabular-nums">{t('plans.perMonth', { amount: formatMoney(plan.monthly_fee_micros, plan.currency) })}</p>
      </div>
      {plan.description && <p className="mt-2 text-sm text-muted">{plan.description}</p>}
      <ul className="mt-4 space-y-1.5 text-sm">
        {channels.map((c) => (
          <li key={c} className="flex items-baseline justify-between gap-3">
            <span>{channelLabel(c)}</span>
            <span className="text-muted tabular-nums">
              {formatNumber(plan.included_messages[c] ?? 0)} · +{formatMoney(plan.overage_price_micros[c] ?? null, plan.currency)}
            </span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex flex-wrap gap-1.5">
        <Badge tone="primary">{modeLabel(plan.default_overage_mode)}</Badge>
        <Badge>{t('plans.margin', { pct: Number(plan.margin_pct) })}</Badge>
        <Badge>
          {plan.monthly_token_allowance ? t('plans.tokens', { amount: formatNumber(plan.monthly_token_allowance) }) : t('plans.unlimitedTokens')}
        </Badge>
        <Badge>{plan.allowed_models.length ? plan.allowed_models.join(', ') : t('plans.anyModel')}</Badge>
      </div>
      <div className="mt-auto flex items-center justify-between gap-2 pt-5">
        <span className="text-sm text-muted">{t('plans.subscribers', { count: plan.subscriptions })}</span>
        <div className="flex gap-1">
          <Button size="sm" variant="secondary" onClick={onEdit} aria-label={t('common.editItem', { name: plan.name })}>
            <Pencil className="size-4" aria-hidden="true" />
            {t('common.edit')}
          </Button>
          <Button size="icon" variant="ghost" onClick={onDelete} aria-label={t('common.deleteItem', { name: plan.name })}>
            <Trash2 className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </Card>
  )
}

/**
 * Plans (admin only): the commercial plans tenants subscribe to, and - under
 * "Costs" - what Flowsdone pays per meter (the catalog every cost, margin
 * and suggested price is computed from).
 */
export function PlansPage() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('plans')
  const plans = usePlans()
  const remove = useDeletePlan()
  const [editing, setEditing] = useState<Plan | null | 'new'>(null)
  const [deleting, setDeleting] = useState<Plan | null>(null)

  const deleteError =
    remove.error instanceof ApiError && remove.error.status === 409 ? t('plans.delete.inUse') : remove.error ? describeError(remove.error) : null

  return (
    <>
      <PageHeader
        title={t('nav.plans')}
        description={t('plans.description')}
        actions={
          tab === 'plans' && (
            <Button onClick={() => setEditing('new')}>
              <Plus className="size-4" aria-hidden="true" />
              {t('plans.new')}
            </Button>
          )
        }
      />
      <div role="tablist" aria-label={t('nav.plans')} className="mb-6 inline-flex rounded-xl bg-surface-muted p-1">
        {(['plans', 'costs'] as const).map((id) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              'cursor-pointer rounded-lg px-4 py-1.5 text-sm font-medium transition',
              tab === id ? 'bg-surface text-foreground shadow-theme-xs' : 'text-muted hover:text-foreground',
            )}
          >
            {t(`plans.tabs.${id}`)}
          </button>
        ))}
      </div>

      {tab === 'costs' ? (
        <CostsPanel />
      ) : plans.isPending ? (
        <Spinner label={t('plans.loading')} className="py-20" />
      ) : plans.isError ? (
        <Alert tone="danger">{t('plans.loadError', { error: describeError(plans.error) })}</Alert>
      ) : plans.data.length === 0 ? (
        <EmptyState icon={Receipt} title={t('plans.empty.title')} description={t('plans.empty.description')} />
      ) : (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {plans.data.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              onEdit={() => setEditing(plan)}
              onDelete={() => {
                remove.reset()
                setDeleting(plan)
              }}
            />
          ))}
        </div>
      )}

      {editing && <PlanDialog plan={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? t('common.deleteItem', { name: deleting.name }) : ''}
        description={t('plans.delete.description')}
        confirmLabel={t('plans.delete.confirm')}
        pending={remove.isPending}
        error={deleteError}
        onCancel={() => setDeleting(null)}
        onConfirm={() =>
          deleting &&
          void remove
            .mutateAsync(deleting.id)
            .then(() => setDeleting(null))
            .catch(() => {})
        }
      />
    </>
  )
}
