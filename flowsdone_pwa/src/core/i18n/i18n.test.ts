import { describe, expect, it } from 'vitest'
import { ca } from './locales/ca'
import { en } from './locales/en'
import { es } from './locales/es'
import { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY, currentLocale, i18n, readStoredLanguage, setLanguage } from './i18n'

const storageWith = (value: string | null) => ({ getItem: () => value })

/** All leaf keys of a catalog, as dotted paths. */
function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => (typeof v === 'string' ? [prefix + k] : keys(v as object, `${prefix}${k}.`)))
}

describe('readStoredLanguage', () => {
  it('español por defecto sin storage, sin valor o con un valor desconocido', () => {
    expect(DEFAULT_LANGUAGE).toBe('es')
    expect(readStoredLanguage(null)).toBe('es')
    expect(readStoredLanguage(storageWith(null))).toBe('es')
    expect(readStoredLanguage(storageWith('fr'))).toBe('es')
  })

  it('respeta un idioma soportado y tolera un storage que lanza', () => {
    expect(readStoredLanguage(storageWith('ca'))).toBe('ca')
    expect(readStoredLanguage(storageWith('en'))).toBe('en')
    expect(readStoredLanguage({ getItem: () => { throw new Error('bloqueado') } })).toBe('es')
  })
})

describe('setLanguage', () => {
  it('cambia el idioma, lo guarda y actualiza <html lang>', () => {
    setLanguage('en')
    expect(i18n.language).toBe('en')
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en')
    expect(document.documentElement.lang).toBe('en')
    expect(i18n.t('nav.settings')).toBe('Settings')
    expect(currentLocale()).toBe('en-GB')

    setLanguage('ca')
    expect(i18n.t('nav.settings')).toBe('Configuració')
    expect(currentLocale()).toBe('ca-ES')
  })

  it('usa las formas de plural de cada idioma', () => {
    setLanguage('es')
    expect(i18n.t('tenants.count.projects', { count: 1 })).toBe('1 proyecto')
    expect(i18n.t('tenants.count.projects', { count: 3 })).toBe('3 proyectos')
    setLanguage('en')
    expect(i18n.t('tenants.count.channels', { count: 1 })).toBe('1 channel')
    expect(i18n.t('tenants.count.channels', { count: 2 })).toBe('2 channels')
  })
})

describe('catálogos', () => {
  it('catalán e inglés tienen exactamente las mismas claves que el español', () => {
    const reference = keys(es).sort()
    expect(keys(ca).sort()).toEqual(reference)
    expect(keys(en).sort()).toEqual(reference)
  })

  it('ninguna traducción usa variables que el español no define', () => {
    const vars = (s: string) => [...s.matchAll(/{{(\w+)}}/g)].map((m) => m[1]).sort()
    const flat = (obj: object, prefix = ''): Record<string, string> =>
      Object.fromEntries(
        Object.entries(obj).flatMap(([k, v]) =>
          typeof v === 'string' ? [[prefix + k, v]] : Object.entries(flat(v as object, `${prefix}${k}.`)),
        ),
      )
    const base = flat(es)
    for (const catalog of [ca, en]) {
      for (const [key, text] of Object.entries(flat(catalog))) {
        expect(vars(text), key).toEqual(vars(base[key]!))
      }
    }
  })
})
