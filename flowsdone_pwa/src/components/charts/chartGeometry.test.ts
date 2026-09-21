import { describe, expect, it } from 'vitest'
import { H, W, linePath, toPoints } from './chartGeometry'

describe('toPoints', () => {
  it('reparte los puntos a lo ancho y deja el máximo arriba y el mínimo abajo', () => {
    const pts = toPoints([10, 30, 20])
    expect(pts).toHaveLength(3)
    expect(pts[0]![0]).toBeLessThan(pts[2]![0])
    expect(pts[1]![1]).toBeLessThan(pts[0]![1]) // 30 más arriba que 10
    expect(pts[1]![1]).toBeLessThan(pts[2]![1])
    for (const [x, y] of pts) {
      expect(x).toBeGreaterThanOrEqual(0)
      expect(x).toBeLessThanOrEqual(W)
      expect(y).toBeGreaterThanOrEqual(0)
      expect(y).toBeLessThanOrEqual(H)
    }
  })

  it('no divide por cero con serie constante o de un solo punto', () => {
    expect(toPoints([5, 5, 5]).every(([, y]) => Number.isFinite(y))).toBe(true)
    expect(toPoints([7])).toHaveLength(1)
  })
})

describe('linePath', () => {
  it('empieza con M y continúa con L', () => {
    expect(linePath([[0, 1], [2, 3]])).toBe('M0.0 1.0 L2.0 3.0')
  })
})
