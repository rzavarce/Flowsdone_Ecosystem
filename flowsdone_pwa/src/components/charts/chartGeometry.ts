/** Chart viewBox width, in SVG units. */
export const W = 600
/** Chart viewBox height, in SVG units. */
export const H = 200
const PAD = 8

/**
 * Converts a series into coordinates within the chart's viewBox.
 *
 * @param values - Numeric series (at least one point).
 * @returns `[x, y]` points; the Y axis starts at 0 and is inverted (higher value = higher up).
 */
export function toPoints(values: readonly number[]): [number, number][] {
  const max = Math.max(...values)
  const min = Math.min(0, ...values) // eje desde 0: no exagera las variaciones
  const range = max - min || 1
  const step = values.length > 1 ? (W - PAD * 2) / (values.length - 1) : 0
  return values.map((v, i) => [PAD + i * step, PAD + (H - PAD * 2) * (1 - (v - min) / range)])
}

/** SVG path of the line joining the points. */
export function linePath(points: [number, number][]): string {
  return points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
}
