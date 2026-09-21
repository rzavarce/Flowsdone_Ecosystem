import { describe, expect, it } from 'vitest'
import { slugify } from './slug'

describe('slugify', () => {
  it.each([
    ['Atención al paciente', 'atencion-al-paciente'],
    ['  Ventas  2026! ', 'ventas-2026'],
    ['Ñandú & Cía.', 'nandu-cia'],
    ['---', ''],
  ])('%s -> %s', (input, expected) => {
    expect(slugify(input)).toBe(expected)
  })
})
