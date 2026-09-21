import { describe, expect, it } from 'vitest'
import { cn } from './cn'
import { formatDelta } from './format'
import { initials } from './initials'

describe('cn', () => {
  it('resuelve conflictos de Tailwind: gana la última clase', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
  })

  it('ignora valores falsy', () => {
    const off = false as boolean
    expect(cn('a', off && 'b', undefined, 'c')).toBe('a c')
  })
})

describe('initials', () => {
  it('toma las dos primeras iniciales en mayúscula', () => {
    expect(initials('ana maría pérez')).toBe('AM')
  })

  it('funciona con un solo nombre y con espacios sobrantes', () => {
    expect(initials('  Roger ')).toBe('R')
  })

  it('devuelve vacío para un nombre vacío', () => {
    expect(initials('   ')).toBe('')
  })
})

describe('formatDelta', () => {
  it('formatea positivo, negativo y cero', () => {
    expect(formatDelta(12.4)).toBe('+12,4 %')
    expect(formatDelta(-14.2)).toBe('−14,2 %')
    expect(formatDelta(0)).toBe('0,0 %')
  })
})
