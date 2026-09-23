import { currentLanguage } from '@/core/i18n/i18n'

/**
 * Formats a percentage delta with a sign and one decimal, using the active
 * language's decimal separator (comma in Spanish/Catalan, dot in English).
 *
 * @example formatDelta(12.4) // '+12,4 %' (es) · '+12.4%' (en)
 */
export function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : ''
  const value = Math.abs(delta).toFixed(1)
  return currentLanguage() === 'en' ? `${sign}${value}%` : `${sign}${value.replace('.', ',')} %`
}
