import { describe, expect, it } from 'vitest'
import { matchesQuery, normalize } from './search'

describe('search', () => {
  it('normaliza mayúsculas y acentos', () => {
    expect(normalize('  José ÁLVAREZ ')).toBe('jose alvarez')
  })

  it('coincide si algún campo contiene la búsqueda; vacía coincide siempre', () => {
    expect(matchesQuery('alva', 'José Álvarez', null)).toBe(true)
    expect(matchesQuery('x', 'abc', undefined)).toBe(false)
    expect(matchesQuery('  ', 'abc')).toBe(true)
  })
})
