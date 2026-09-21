/**
 * Formatea una variación porcentual con signo y coma decimal.
 *
 * @example formatDelta(12.4) // '+12,4 %'
 */
export function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '−' : ''
  return `${sign}${Math.abs(delta).toFixed(1).replace('.', ',')} %`
}
