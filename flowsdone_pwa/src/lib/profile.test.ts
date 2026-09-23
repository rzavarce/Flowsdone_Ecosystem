import { describe, expect, it } from 'vitest'
import { cleanLinks, phoneError, profileFieldsErrors, urlError } from './profile'

describe('phoneError', () => {
  it('acepta vacío y formatos habituales', () => {
    for (const ok of ['', '  ', '+34 600 123 456', '(0212) 555-1234', '600.123.456']) expect(phoneError(ok)).toBeNull()
  })

  it('rechaza letras y valores demasiado cortos', () => {
    expect(phoneError('llámame')).toBe('profile.errors.phone')
    expect(phoneError('12')).toBe('profile.errors.phone')
  })
})

describe('urlError', () => {
  it('acepta vacío y URLs http(s)', () => {
    expect(urlError('')).toBeNull()
    expect(urlError('https://www.linkedin.com/in/x')).toBeNull()
    expect(urlError('http://example.com')).toBeNull()
  })

  it('rechaza esquemas peligrosos o direcciones incompletas', () => {
    for (const bad of ['javascript:alert(1)', 'ftp://x.com', 'linkedin.com/in/x', 'https://']) {
      expect(urlError(bad)).toBe('profile.errors.url')
    }
  })
})

describe('cleanLinks', () => {
  it('quita las vacías y recorta el resto', () => {
    expect(cleanLinks({ website: ' https://a.dev ', x: '', linkedin: '   ' })).toEqual({ website: 'https://a.dev' })
  })
})

describe('profileFieldsErrors', () => {
  it('devuelve un error por campo inválido y nada si todo está bien', () => {
    expect(profileFieldsErrors({ phone: '', address: '', social_links: {} })).toEqual({})
    expect(
      profileFieldsErrors({ phone: 'abc', address: 'x'.repeat(301), social_links: { instagram: 'insta' } }),
    ).toEqual({ phone: 'profile.errors.phone', address: 'profile.errors.address', instagram: 'profile.errors.url' })
  })
})
