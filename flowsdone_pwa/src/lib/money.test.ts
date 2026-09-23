import { describe, expect, it } from 'vitest'
import { currentPeriod, formatMoney, formatNumber, microsToInput, parseMoney, recentPeriods } from './money'

describe('parseMoney', () => {
  it.each([
    ['0,02', 20_000],
    ['0.02', 20_000],
    ['29', 29_000_000],
    ['1.234,5', 1_234_500_000],
    ['1,234.5', 1_234_500_000],
    [' 3 € ', 3_000_000],
    ['0,0012', 1_200],
  ])('%s -> %d micros', (text, micros) => {
    expect(parseMoney(text)).toBe(micros)
  })

  it.each(['', '   ', 'abc', '-1', '1,2,x'])('rechaza %j', (text) => {
    expect(parseMoney(text)).toBeNull()
  })
})

describe('formatMoney', () => {
  it('usa 2 decimales para importes normales y hasta 4 para fracciones de céntimo', () => {
    expect(formatMoney(49_000_000)).toMatch(/49,00\s€/)
    expect(formatMoney(1_150)).toMatch(/0,0012\s€/)
    expect(formatMoney(null)).toBe('—')
  })
})

describe('formatNumber y microsToInput', () => {
  it('formatea cantidades y deja importes editables con coma decimal', () => {
    expect(formatNumber('1500')).toBe('1500')
    expect(formatNumber(null)).toBe('—')
    expect(microsToInput(20_000)).toBe('0,02')
    expect(microsToInput(null)).toBe('')
  })
})

describe('periodos', () => {
  it('lista los meses hacia atrás cruzando el año', () => {
    expect(currentPeriod(new Date('2026-09-23T10:00:00Z'))).toBe('2026-09')
    expect(recentPeriods(3, '2026-02')).toEqual(['2026-02', '2026-01', '2025-12'])
  })
})
