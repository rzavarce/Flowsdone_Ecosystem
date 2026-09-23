import { currentLocale } from '@/core/i18n/i18n'

/** Micro-units per currency unit: the gateway sends every amount as an integer of millionths. */
export const MICROS = 1_000_000

/**
 * Formats an amount in micro-units as currency in the active language.
 * Shows up to 4 decimals for small amounts (per-message prices are often
 * fractions of a cent) and 2 otherwise.
 *
 * @example formatMoney(20_000) // '0,02 €' (es)
 * @example formatMoney(1_150) // '0,0012 €' (es)
 */
export function formatMoney(micros: number | null | undefined, currency = 'EUR'): string {
  if (micros === null || micros === undefined) return '—'
  const value = micros / MICROS
  const small = value !== 0 && Math.abs(value) < 0.1
  return new Intl.NumberFormat(currentLocale(), {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: small ? 4 : 2,
  }).format(value)
}

/** Formats a count or decimal quantity (tokens, messages) with the active language's grouping. */
export function formatNumber(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return new Intl.NumberFormat(currentLocale(), { maximumFractionDigits: 2 }).format(Number(value))
}

/**
 * Parses an amount typed by a person ("0,02", "1.234,5", "29") into
 * micro-units. Accepts comma or dot as the decimal separator (the last one
 * found wins when both appear).
 *
 * @returns The amount in micro-units, or `null` if the text is empty or not a
 *   valid non-negative number.
 */
export function parseMoney(text: string): number | null {
  const raw = text.trim().replace(/\s|€/g, '')
  if (!raw) return null
  const lastSep = Math.max(raw.lastIndexOf(','), raw.lastIndexOf('.'))
  const normalized =
    lastSep === -1 ? raw : raw.slice(0, lastSep).replace(/[.,]/g, '') + '.' + raw.slice(lastSep + 1)
  if (!/^\d+(\.\d+)?$/.test(normalized)) return null
  return Math.round(Number(normalized) * MICROS)
}

/** Micro-units as a plain editable number ("0.02" -> shown with the language's separator). */
export function microsToInput(micros: number | null | undefined): string {
  if (micros === null || micros === undefined) return ''
  const text = String(micros / MICROS)
  return currentLocale().startsWith('en') ? text : text.replace('.', ',')
}

/** Current period as `YYYY-MM` (UTC). */
export function currentPeriod(now = new Date()): string {
  return now.toISOString().slice(0, 7)
}

/** The `count` periods up to (and including) `from`, newest first. */
export function recentPeriods(count: number, from = currentPeriod()): string[] {
  const [year, month] = from.split('-').map(Number) as [number, number]
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(Date.UTC(year, month - 1 - i, 1))
    return d.toISOString().slice(0, 7)
  })
}

/** A `YYYY-MM` period as a month name in the active language ("septiembre de 2026"). */
export function formatPeriod(period: string): string {
  const [year, month] = period.split('-').map(Number) as [number, number]
  return new Intl.DateTimeFormat(currentLocale(), { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year, month - 1, 1)),
  )
}
