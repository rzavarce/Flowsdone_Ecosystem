import { Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { usePlans, useSaveSubscription, useSubscription } from '@/core/admin/billingHooks'
import type { OverageMode, Plan, Subscription } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { modeLabel } from '@/features/billing/labels'
import { formatMoney, microsToInput, parseMoney } from '@/lib/money'
import { useTranslation } from 'react-i18next'

const FORM_ID = 'subscription-form'
const MODES: OverageMode[] = ['notify', 'overage', 'hard_stop']

/** Assign/change a tenant's plan and its overrides (admin). */
function SubscriptionDialog({
  tenantId,
  tenantName,
  current,
  plans,
  onClose,
}: {
  tenantId: string
  tenantName: string
  current: Subscription | null
  plans: Plan[]
  onClose: () => void
}) {
  const { t } = useTranslation()
  const save = useSaveSubscription()
  const assignable = plans.filter((p) => p.active || p.id === current?.plan_id)
  const [planId, setPlanId] = useState(current?.plan_id ?? assignable[0]?.id ?? '')
  const [mode, setMode] = useState<OverageMode | ''>(current?.overage_mode ?? '')
  const [cap, setCap] = useState(microsToInput(current?.spending_cap_micros ?? null))
  const [capError, setCapError] = useState<string>()
  const plan = plans.find((p) => p.id === planId)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const capMicros = cap.trim() ? parseMoney(cap) : null
    if (cap.trim() && capMicros === null) {
      setCapError(t('plans.errors.money'))
      return
    }
    try {
      await save.mutateAsync({
        tenantId,
        input: { plan_id: planId, overage_mode: mode || null, spending_cap_micros: capMicros },
      })
      onClose()
    } catch {
      // El error queda en save.error.
    }
  }

  return (
    <Dialog
      open
      onClose={save.isPending ? () => {} : onClose}
      title={t('subscription.title')}
      description={tenantName}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending || !planId}>
            {save.isPending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label={t('subscription.fields.plan')}>
          <Select value={planId} onChange={(e) => setPlanId(e.target.value)}>
            {assignable.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {t('plans.perMonth', { amount: formatMoney(p.monthly_fee_micros, p.currency) })}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('subscription.fields.mode')} hint={t(`plans.modes.${mode || plan?.default_overage_mode || 'notify'}.description`)}>
          <Select value={mode} onChange={(e) => setMode(e.target.value as OverageMode | '')}>
            <option value="">{t('subscription.fields.modeDefault', { mode: plan ? modeLabel(plan.default_overage_mode) : '—' })}</option>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {modeLabel(m)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('subscription.fields.cap')} hint={t('subscription.fields.capHint')} error={capError}>
          <Input inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} />
        </Field>
        {save.error && <Alert tone="danger">{describeError(save.error)}</Alert>}
      </form>
    </Dialog>
  )
}

/** Props for {@link SubscriptionCard}. */
export interface SubscriptionCardProps {
  tenantId: string
  tenantName: string
  /** Admin: can assign, change and remove the plan (the gateway enforces it too). */
  canEdit: boolean
}

/**
 * The tenant's plan: which one, what happens past the included messages and
 * the overage spending cap. Admins assign/change/remove it; managers see it.
 */
export function SubscriptionCard({ tenantId, tenantName, canEdit }: SubscriptionCardProps) {
  const { t } = useTranslation()
  const subscription = useSubscription(tenantId)
  const plans = usePlans(canEdit)
  const save = useSaveSubscription()
  const [editing, setEditing] = useState(false)
  const [removing, setRemoving] = useState(false)
  const sub = subscription.data

  return (
    <Card>
      <CardHeader
        title={t('subscription.title')}
        description={t('subscription.description')}
        action={
          canEdit && (
            <div className="flex gap-1">
              <Button size="sm" variant="secondary" onClick={() => setEditing(true)} disabled={subscription.isPending || plans.isPending}>
                <Pencil className="size-4" aria-hidden="true" />
                {sub ? t('subscription.change') : t('subscription.assign')}
              </Button>
              {sub && (
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => {
                    save.reset()
                    setRemoving(true)
                  }}
                  aria-label={t('subscription.remove')}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              )}
            </div>
          )
        }
      />
      <div className="p-5 pt-4 sm:px-6">
        {subscription.isPending ? (
          <Spinner label={t('subscription.loading')} />
        ) : subscription.isError ? (
          <Alert tone="danger">{describeError(subscription.error)}</Alert>
        ) : !sub ? (
          <p className="text-sm text-muted">{t('subscription.none')}</p>
        ) : (
          <div className="space-y-1 text-sm">
            <p className="text-base font-semibold">{sub.plan_name}</p>
            <p className="text-muted">{t('subscription.since', { date: new Date(sub.started_at).toLocaleDateString(currentLocale()) })}</p>
            <p>{t('subscription.mode', { mode: modeLabel(sub.effective_overage_mode) })}</p>
            <p className="text-muted">
              {sub.spending_cap_micros === null ? t('subscription.noCap') : t('subscription.cap', { amount: formatMoney(sub.spending_cap_micros) })}
            </p>
          </div>
        )}
        {canEdit && plans.data?.length === 0 && <p className="mt-3 text-xs text-muted">{t('subscription.noPlans')}</p>}
      </div>

      {editing && plans.data && (
        <SubscriptionDialog tenantId={tenantId} tenantName={tenantName} current={sub ?? null} plans={plans.data} onClose={() => setEditing(false)} />
      )}
      <ConfirmDialog
        open={removing}
        title={t('subscription.removeTitle')}
        description={t('subscription.removeDescription')}
        confirmLabel={t('subscription.removeConfirm')}
        pending={save.isPending}
        error={save.error ? describeError(save.error) : null}
        onCancel={() => setRemoving(false)}
        onConfirm={() =>
          void save
            .mutateAsync({ tenantId, input: null })
            .then(() => setRemoving(false))
            .catch(() => {})
        }
      />
    </Card>
  )
}
