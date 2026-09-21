export const W = 600
export const H = 200
const PAD = 8

/**
 * Convierte una serie en coordenadas dentro del viewBox del gráfico.
 *
 * @param values - Serie numérica (al menos un punto).
 * @returns Puntos `[x, y]`; el eje Y arranca en 0 y está invertido (mayor valor = más arriba).
 */
export function toPoints(values: readonly number[]): [number, number][] {
  const max = Math.max(...values)
  const min = Math.min(0, ...values) // eje desde 0: no exagera las variaciones
  const range = max - min || 1
  const step = values.length > 1 ? (W - PAD * 2) / (values.length - 1) : 0
  return values.map((v, i) => [PAD + i * step, PAD + (H - PAD * 2) * (1 - (v - min) / range)])
}

/** Path SVG de la línea que une los puntos. */
export function linePath(points: [number, number][]): string {
  return points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
}
