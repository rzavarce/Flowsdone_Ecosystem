import { Plus, Sparkles, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { usePricingInsight, useSavePlan } from '@/core/admin/billingHooks'
import type { OverageMode, Plan, PlanInput } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { channelLabel, modeLabel } from '@/features/billing/labels'
import { CHANNEL_TYPE_LIST } from '@/features/channels/channelTypes'
import { formatMoney, microsToInput, parseMoney } from '@/lib/money'
import { useTranslation } from 'react-i18next'

/** One editable "channel -> included messages / overage price" row. */
interface ChannelRow {
  channel: string
  included: string
  price: string
}

/** Props for {@link PlanDialog}. */
export interface PlanDialogProps {
  /** Plan to edit, or `null` to create one. */
  plan: Plan | null
  onClose: () => void
}

const FORM_ID = 'plan-form'
const CODE = /^[a-z0-9][a-z0-9_-]*$/
const MODES: OverageMode[] = ['notify', 'overage', 'hard_stop']
const INT = /^\d+$/

/** Rows from a plan's two per-channel maps (union of their channels, `*` last). */
function rowsOf(plan: Plan | null): ChannelRow[] {
  if (!plan) return [{ channel: '*', included: '', price: '' }]
  const channels = [...new Set([...Object.keys(plan.included_messages), ...Object.keys(plan.overage_price_micros)])]
  channels.sort((a, b) => (a === '*' ? 1 : b === '*' ? -1 : a.localeCompare(b)))
  return channels.map((channel) => ({
    channel,
    included: plan.included_messages[channel] === undefined ? '' : String(plan.included_messages[channel]),
    price: microsToInput(plan.overage_price_micros[channel]),
  }))
}

/**
 * Create/edit a plan (admin): fee, included messages and overage price per
 * channel (`*` = any other channel), target margin, overage mode, allowed
 * models and fair-use tokens. When editing, shows the pricing insight - the
 * average cost per message over the last 30 days and the price the margin
 * suggests - and can copy the suggested prices into the form.
 */
export function PlanDialog({ plan, onClose }: PlanDialogProps) {
  const { t } = useTranslation()
  const save = useSavePlan()
  const insight = usePricingInsight(plan?.id)
  const [code, setCode] = useState(plan?.code ?? '')
  const [name, setName] = useState(plan?.name ?? '')
  const [description, setDescription] = useState(plan?.description ?? '')
  const [fee, setFee] = useState(microsToInput(plan?.monthly_fee_micros ?? null))
  const [margin, setMargin] = useState(plan ? String(Number(plan.margin_pct)) : '30')
  const [mode, setMode] = useState<OverageMode>(plan?.default_overage_mode ?? 'notify')
  const [models, setModels] = useState(plan?.allowed_models.join(', ') ?? '')
  const [tokens, setTokens] = useState(plan?.monthly_token_allowance ? String(plan.monthly_token_allowance) : '')
  const [active, setActive] = useState(plan?.active ?? true)
  const [rows, setRows] = useState<ChannelRow[]>(() => rowsOf(plan))
  const [errors, setErrors] = useState<Record<string, string>>({})

  const used = new Set(rows.map((r) => r.channel))
  const available = ['*', ...CHANNEL_TYPE_LIST.map((c) => c.type)].filter((c) => !used.has(c))
  const setRow = (index: number, patch: Partial<ChannelRow>) =>
    setRows((current) => current.map((r, i) => (i === index ? { ...r, ...patch } : r)))

  function applySuggested() {
    const suggested = insight.data?.channels.filter((c) => c.suggested_price_micros !== null) ?? []
    setRows((current) => {
      const next = current.map((r) => {
        const s = suggested.find((c) => c.channel_type === r.channel)
        return s ? { ...r, price: microsToInput(s.suggested_price_micros) } : r
      })
      for (const s of suggested) {
        if (!next.some((r) => r.channel === s.channel_type)) {
          next.push({ channel: s.channel_type, included: '', price: microsToInput(s.suggested_price_micros) })
        }
      }
      return next
    })
  }

  function validate(): PlanInput | null {
    const problems: Record<string, string> = {}
    if (!CODE.test(code)) problems.code = t('plans.errors.code')
    if (!name.trim()) problems.name = t('common.nameRequired')
    const feeMicros = fee.trim() ? parseMoney(fee) : 0
    if (feeMicros === null) problems.fee = t('plans.errors.money')
    const marginValue = margin.trim().replace(',', '.')
    if (!/^\d+(\.\d+)?$/.test(marginValue)) problems.margin = t('plans.errors.margin')
    if (tokens.trim() && !INT.test(tokens.trim())) problems.tokens = t('plans.errors.number')
    const included: Record<string, number> = {}
    const prices: Record<string, number> = {}
    rows.forEach((r, i) => {
      if (r.included.trim()) {
        if (!INT.test(r.included.trim())) problems[`included-${i}`] = t('plans.errors.number')
        else included[r.channel] = Number(r.included.trim())
      }
      if (r.price.trim()) {
        const micros = parseMoney(r.price)
        if (micros === null) problems[`price-${i}`] = t('plans.errors.money')
        else prices[r.channel] = micros
      }
    })
    setErrors(problems)
    if (Object.keys(problems).length) return null
    return {
      code,
      name: name.trim(),
      description: description.trim() || null,
      monthly_fee_micros: feeMicros ?? 0,
      margin_pct: marginValue,
      default_overage_mode: mode,
      allowed_models: models.split(',').map((m) => m.trim()).filter(Boolean),
      monthly_token_allowance: tokens.trim() ? Number(tokens.trim()) : null,
      active,
      included_messages: included,
      overage_price_micros: prices,
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const input = validate()
    if (!input) return
    try {
      await save.mutateAsync({ id: plan?.id, input })
      onClose()
    } catch {
      // El error queda en save.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={save.isPending ? () => {} : onClose}
      title={plan ? t('plans.dialog.editTitle', { name: plan.name }) : t('plans.dialog.createTitle')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending}>
            {save.isPending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('plans.fields.name')} error={errors.name}>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label={t('plans.fields.code')} hint={t('plans.fields.codeHint')} error={errors.code}>
            <Input value={code} onChange={(e) => setCode(e.target.value.toLowerCase())} className="font-mono" />
          </Field>
        </div>
        <Field label={t('plans.fields.description')}>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('plans.fields.fee')} error={errors.fee}>
            <Input inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} placeholder="49" />
          </Field>
          <Field label={t('plans.fields.margin')} hint={t('plans.fields.marginHint')} error={errors.margin}>
            <Input inputMode="decimal" value={margin} onChange={(e) => setMargin(e.target.value)} />
          </Field>
        </div>

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-foreground/80">{t('plans.fields.channels')}</legend>
          <p className="text-xs text-muted">{t('plans.fields.channelsHint')}</p>
          {rows.map((row, i) => (
            <div key={row.channel} className="grid grid-cols-[1fr_6rem_7rem_auto] items-start gap-2">
              <span className="flex h-11 items-center truncate text-sm font-medium">{channelLabel(row.channel)}</span>
              <Field label={t('plans.fields.included')} error={errors[`included-${i}`]}>
                <Input inputMode="numeric" value={row.included} onChange={(e) => setRow(i, { included: e.target.value })} />
              </Field>
              <Field label={t('plans.fields.overagePrice')} error={errors[`price-${i}`]}>
                <Input inputMode="decimal" value={row.price} onChange={(e) => setRow(i, { price: e.target.value })} />
              </Field>
              <Button
                variant="ghost"
                size="icon"
                className="mt-7"
                onClick={() => setRows((current) => current.filter((_, j) => j !== i))}
                aria-label={t('plans.fields.removeChannel', { channel: channelLabel(row.channel) })}
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>
          ))}
          {available.length > 0 && (
            <div className="flex items-center gap-2">
              <Select
                aria-label={t('plans.fields.addChannel')}
                value=""
                onChange={(e) => e.target.value && setRows((current) => [...current, { channel: e.target.value, included: '', price: '' }])}
                className="max-w-xs"
              >
                <option value="">{t('plans.fields.addChannel')}</option>
                {available.map((c) => (
                  <option key={c} value={c}>
                    {channelLabel(c)}
                  </option>
                ))}
              </Select>
              <Plus className="size-4 text-muted" aria-hidden="true" />
            </div>
          )}
        </fieldset>

        <section className="space-y-2 rounded-xl border border-border p-4" aria-label={t('plans.insight.title')}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">{t('plans.insight.title')}</h3>
            {plan && insight.data && (
              <Button size="sm" variant="secondary" onClick={applySuggested}>
                <Sparkles className="size-4" aria-hidden="true" />
                {t('plans.insight.useSuggested')}
              </Button>
            )}
          </div>
          {!plan ? (
            <p className="text-xs text-muted">{t('plans.insight.afterSave')}</p>
          ) : insight.isPending ? (
            <Spinner label={t('plans.loading')} />
          ) : insight.isError ? (
            <Alert tone="danger">{describeError(insight.error)}</Alert>
          ) : (
            <>
              <p className="text-xs text-muted">
                {t('plans.insight.description', { days: insight.data.days })}{' '}
                {insight.data.sample === 'plan' ? t('plans.insight.samplePlan') : t('plans.insight.samplePlatform')}
              </p>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="py-1 font-medium">{t('plans.fields.channel')}</th>
                    <th className="py-1 font-medium">{t('plans.insight.avgCost')}</th>
                    <th className="py-1 font-medium">{t('plans.insight.suggested')}</th>
                    <th className="py-1 font-medium">{t('plans.insight.marginAtConfigured')}</th>
                  </tr>
                </thead>
                <tbody>
                  {insight.data.channels.map((c) => (
                    <tr key={c.channel_type} className="border-t border-border">
                      <td className="py-1.5">{channelLabel(c.channel_type)}</td>
                      <td className="py-1.5 tabular-nums">{c.avg_cost_micros === null ? t('plans.insight.noData') : formatMoney(c.avg_cost_micros)}</td>
                      <td className="py-1.5 tabular-nums">{formatMoney(c.suggested_price_micros)}</td>
                      <td className="py-1.5 tabular-nums">{c.margin_at_configured_pct === null ? '—' : `${c.margin_at_configured_pct} %`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>

        <Field label={t('plans.fields.mode')} hint={t(`plans.modes.${mode}.description`)}>
          <Select value={mode} onChange={(e) => setMode(e.target.value as OverageMode)}>
            {MODES.map((m) => (
              <option key={m} value={m}>
                {modeLabel(m)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('plans.fields.allowedModels')} hint={t('plans.fields.allowedModelsHint')}>
          <Input value={models} onChange={(e) => setModels(e.target.value)} className="font-mono" />
        </Field>
        <Field label={t('plans.fields.tokenAllowance')} hint={t('plans.fields.tokenAllowanceHint')} error={errors.tokens}>
          <Input inputMode="numeric" value={tokens} onChange={(e) => setTokens(e.target.value)} />
        </Field>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="size-4 accent-primary" />
          {t('plans.fields.active')}
        </label>
        {save.error && <Alert tone="danger">{describeError(save.error)}</Alert>}
      </form>
    </Dialog>
  )
}
