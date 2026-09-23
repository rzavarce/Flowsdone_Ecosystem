import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { usePlans, useSaveSubscription, useSubscription } from '@/core/admin/billingHooks'
import type { OverageMode, Plan, Subscription } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { modeLabel } from '@/features/billing/labels'
import { cn } from '@/lib/cn'
import { formatMoney, formatNumber, microsToInput, parseMoney } from '@/lib/money'
import { StepFrame } from './StepFrame'
import { useTranslation } from 'react-i18next'

const MODES: OverageMode[] = ['notify', 'overage', 'hard_stop']

/** Step 2: the plan (cards with what each one includes), overage mode and spending cap. */
export function PlanStep({ tenantId, onDone, onBack }: { tenantId: string; onDone: () => void; onBack: () => void }) {
  const { t } = useTranslation()
  const plans = usePlans()
  const subscription = useSubscription(tenantId)
  if (plans.isPending || subscription.isPending) return <Spinner label={t('onboarding.loading')} className="py-16" />
  if (plans.isError) return <Alert tone="danger">{describeError(plans.error)}</Alert>
  return <PlanForm tenantId={tenantId} plans={plans.data.filter((p) => p.active)} current={subscription.data ?? null} onDone={onDone} onBack={onBack} />
}

function PlanForm({
  tenantId,
  plans,
  current,
  onDone,
  onBack,
}: {
  tenantId: string
  plans: Plan[]
  current: Subscription | null
  onDone: () => void
  onBack: () => void
}) {
  const { t } = useTranslation()
  const save = useSaveSubscription()
  const [planId, setPlanId] = useState(current?.plan_id ?? '')
  const [mode, setMode] = useState<OverageMode | ''>(current?.overage_mode ?? '')
  const [cap, setCap] = useState(microsToInput(current?.spending_cap_micros ?? null))
  const [error, setError] = useState<string | null>(null)
  const plan = plans.find((p) => p.id === planId)
  const effective = mode || plan?.default_overage_mode

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!planId) return setError(t('onboarding.plan.required'))
    const capMicros = cap.trim() ? parseMoney(cap) : null
    if (cap.trim() && capMicros === null) return setError(t('plans.errors.money'))
    setError(null)
    try {
      await save.mutateAsync({ tenantId, input: { plan_id: planId, overage_mode: mode || null, spending_cap_micros: capMicros } })
      onDone()
    } catch {
      // El error queda en save.error.
    }
  }

  return (
    <StepFrame
      title={t('onboarding.steps.plan')}
      description={t('onboarding.plan.description')}
      onSubmit={submit}
      onBack={onBack}
      pending={save.isPending}
      error={error ?? (save.error ? describeError(save.error) : null)}
    >
      {plans.length === 0 ? (
        <Alert tone="info">{t('onboarding.plan.noPlans')}</Alert>
      ) : (
        <div role="radiogroup" aria-label={t('onboarding.steps.plan')} className="grid gap-4 md:grid-cols-3">
          {plans.map((p) => {
            const selected = p.id === planId
            const text = p.included_messages['*'] ?? Object.values(p.included_messages)[0] ?? 0
            const voice = p.included_messages.voice
            return (
              <button
                key={p.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPlanId(p.id)}
                className={cn(
                  'cursor-pointer rounded-card border p-4 text-left transition',
                  selected ? 'border-primary bg-primary/5 ring-2 ring-primary/30' : 'border-border hover:bg-surface-muted',
                )}
              >
                <span className="block text-lg font-semibold">{p.name}</span>
                <span className="block text-sm tabular-nums">{t('plans.perMonth', { amount: formatMoney(p.monthly_fee_micros, p.currency) })}</span>
                <span className="mt-2 block text-xs text-muted">{t('onboarding.plan.included', { amount: formatNumber(text) })}</span>
                {voice ? <span className="block text-xs text-muted">{t('onboarding.plan.voice', { amount: formatNumber(voice) })}</span> : null}
                <span className="mt-2 block text-xs text-muted">{modeLabel(p.default_overage_mode)}</span>
                {p.description && <span className="mt-2 block text-xs text-muted">{p.description}</span>}
              </button>
            )
          })}
        </div>
      )}
      {plan && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Field label={t('subscription.fields.mode')} hint={t(`plans.modes.${effective ?? 'notify'}.description`)}>
            <Select value={mode} onChange={(e) => setMode(e.target.value as OverageMode | '')}>
              <option value="">{t('subscription.fields.modeDefault', { mode: modeLabel(plan.default_overage_mode) })}</option>
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {modeLabel(m)}
                </option>
              ))}
            </Select>
          </Field>
          {effective === 'overage' && (
            <Field label={t('subscription.fields.cap')} hint={t('subscription.fields.capHint')}>
              <Input inputMode="decimal" value={cap} onChange={(e) => setCap(e.target.value)} />
            </Field>
          )}
        </div>
      )}
    </StepFrame>
  )
}
