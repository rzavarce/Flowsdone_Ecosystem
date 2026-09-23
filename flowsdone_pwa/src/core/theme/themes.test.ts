import { describe, expect, it } from 'vitest'
import html from '../../../index.html?raw'
import { DEFAULT_MODE, DEFAULT_THEME, THEMES, THEME_STORAGE_KEY, readStoredTheme, resolveMode } from './themes'

const storageWith = (value: string | null) => ({ getItem: () => value })

describe('resolveMode', () => {
  it('respeta light y dark sin importar el sistema', () => {
    expect(resolveMode('light', true)).toBe('light')
    expect(resolveMode('dark', false)).toBe('dark')
  })

  it('en system delega en la preferencia del SO', () => {
    expect(resolveMode('system', true)).toBe('dark')
    expect(resolveMode('system', false)).toBe('light')
  })
})

describe('readStoredTheme', () => {
  it('devuelve defaults sin storage', () => {
    expect(readStoredTheme(null)).toEqual({ theme: DEFAULT_THEME, mode: DEFAULT_MODE })
  })

  it('devuelve defaults si no hay nada guardado', () => {
    expect(readStoredTheme(storageWith(null))).toEqual({ theme: DEFAULT_THEME, mode: DEFAULT_MODE })
  })

  it('lee un tema válido', () => {
    const raw = JSON.stringify({ theme: 'agentic', mode: 'dark' })
    expect(readStoredTheme(storageWith(raw))).toEqual({ theme: 'agentic', mode: 'dark' })
  })

  it('reemplaza por default un preset que ya no existe, conservando el modo', () => {
    const raw = JSON.stringify({ theme: 'retirado', mode: 'light' })
    expect(readStoredTheme(storageWith(raw))).toEqual({ theme: DEFAULT_THEME, mode: 'light' })
  })

  it('tolera JSON roto', () => {
    expect(readStoredTheme(storageWith('{no-json'))).toEqual({ theme: DEFAULT_THEME, mode: DEFAULT_MODE })
  })

  it('tolera un storage que lanza', () => {
    const throwing = {
      getItem: () => {
        throw new Error('bloqueado')
      },
    }
    expect(readStoredTheme(throwing)).toEqual({ theme: DEFAULT_THEME, mode: DEFAULT_MODE })
  })

  it('usa la clave esperada por el script anti-flash de index.html', () => {
    expect(THEME_STORAGE_KEY).toBe('fd-theme')
  })

  it('lee el preset admin (estilo TailAdmin)', () => {
    const raw = JSON.stringify({ theme: 'admin', mode: 'light' })
    expect(readStoredTheme(storageWith(raw))).toEqual({ theme: 'admin', mode: 'light' })
  })
})

describe('catálogo de templates', () => {
  it('admin es el template por defecto y encabeza el catálogo', () => {
    expect(DEFAULT_THEME).toBe('admin')
    expect(THEMES[0]?.id).toBe('admin')
  })

  it('el script anti-flash de index.html conoce los mismos ids y el mismo default', () => {
    const list = /var themes = \[([^\]]*)\]/.exec(html)?.[1] ?? ''
    const ids = [...list.matchAll(/'([^']+)'/g)].map((m) => m[1])
    expect(ids).toEqual(THEMES.map((t) => t.id))
    expect(html).toContain(`s.theme : '${DEFAULT_THEME}'`)
  })
})
