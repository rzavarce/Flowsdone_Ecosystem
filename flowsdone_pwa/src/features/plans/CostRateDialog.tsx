import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateCostRate } from '@/core/admin/billingHooks'
import type { CostRate, CostRateInput } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { kindLabel, unitLabel } from '@/features/billing/labels'
import { parseMoney } from '@/lib/money'
import { useTranslation } from 'react-i18next'

/** Props for {@link CostRateDialog}. */
export interface CostRateDialogProps {
  /** Prefill (e.g. from a meter without rate). */
  initial?: Partial<Pick<CostRateInput, 'kind' | 'provider' | 'sku' | 'unit'>>
  onClose: () => void
}

const FORM_ID = 'cost-rate-form'
const KINDS: CostRate['kind'][] = ['llm', 'channel', 'platform']
const UNITS = ['input_token', 'output_token', 'cached_input_token', 'message']

/**
 * New rate (admin): what Flowsdone pays for a meter from a date on. LLM
 * tokens default to "per million", messages to "per unit". Changing a price
 * means adding a new rate, never editing one, so past usage keeps its price.
 */
export function CostRateDialog({ initial, onClose }: CostRateDialogProps) {
  const { t } = useTranslation()
  const create = useCreateCostRate()
  const [kind, setKind] = useState<CostRate['kind']>(initial?.kind ?? 'llm')
  const [provider, setProvider] = useState(initial?.provider ?? '')
  const [sku, setSku] = useState(initial?.sku ?? '')
  const [unit, setUnit] = useState(initial?.unit ?? (initial?.kind === 'llm' || !initial?.kind ? 'input_token' : 'message'))
  const [price, setPrice] = useState('')
  const [perQuantity, setPerQuantity] = useState(unit.endsWith('token') ? '1000000' : '1')
  const [validFrom, setValidFrom] = useState('')
  const [note, setNote] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  function changeUnit(next: string) {
    setUnit(next)
    setPerQuantity(next.endsWith('token') ? '1000000' : '1')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const problems: Record<string, string> = {}
    if (!provider.trim()) problems.provider = t('common.fieldRequired', { field: t('costs.dialog.provider') })
    if (!sku.trim()) problems.sku = t('common.fieldRequired', { field: t('costs.dialog.sku') })
    const priceMicros = parseMoney(price)
    if (priceMicros === null) problems.price = t('plans.errors.money')
    if (!/^[1-9]\d*$/.test(perQuantity.trim())) problems.perQuantity = t('plans.errors.number')
    setErrors(problems)
    if (Object.keys(problems).length) return
    try {
      await create.mutateAsync({
        kind,
        provider: provider.trim(),
        sku: sku.trim(),
        unit,
        price_micros: priceMicros ?? 0,
        per_quantity: Number(perQuantity.trim()),
        valid_from: validFrom ? new Date(`${validFrom}T00:00:00Z`).toISOString() : undefined,
        note: note.trim() || null,
      })
      onClose()
    } catch {
      // El error queda en create.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={create.isPending ? () => {} : onClose}
      title={t('costs.dialog.title')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={create.isPending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={create.isPending}>
            {create.isPending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('costs.dialog.kind')}>
            <Select value={kind} onChange={(e) => setKind(e.target.value as CostRate['kind'])}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {kindLabel(k)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t('costs.dialog.unit')}>
            <Select value={unit} onChange={(e) => changeUnit(e.target.value)}>
              {UNITS.map((u) => (
                <option key={u} value={u}>
                  {unitLabel(u)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label={t('costs.dialog.provider')} hint={t('costs.dialog.providerHint')} error={errors.provider}>
          <Input value={provider} onChange={(e) => setProvider(e.target.value)} className="font-mono" />
        </Field>
        <Field label={t('costs.dialog.sku')} hint={t('costs.dialog.skuHint')} error={errors.sku}>
          <Input value={sku} onChange={(e) => setSku(e.target.value)} className="font-mono" />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('costs.dialog.price')} error={errors.price}>
            <Input inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0,37" />
          </Field>
          <Field label={t('costs.dialog.perQuantity')} hint={t('costs.dialog.perQuantityHint')} error={errors.perQuantity}>
            <Input inputMode="numeric" value={perQuantity} onChange={(e) => setPerQuantity(e.target.value)} />
          </Field>
        </div>
        <Field label={t('costs.dialog.validFrom')} hint={t('costs.dialog.validFromHint')}>
          <Input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
        </Field>
        <Field label={t('costs.dialog.note')}>
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('costs.dialog.notePlaceholder')} />
        </Field>
        {create.error && <Alert tone="danger">{describeError(create.error)}</Alert>}
      </form>
    </Dialog>
  )
}
