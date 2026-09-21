import { describe, expect, it } from 'vitest'
import type { ChannelType } from '@/core/admin/types'
import { CHANNEL_TYPES, CHANNEL_TYPE_LIST, maskExternalId, slugify } from './channelTypes'

const ALL: ChannelType[] = ['facebook', 'instagram', 'twitter', 'whatsapp_evolution', 'telegram', 'tiktok', 'voice']

describe('catálogo de canales', () => {
  it('cubre exactamente los siete canales que soporta el gateway', () => {
    expect(Object.keys(CHANNEL_TYPES).sort()).toEqual([...ALL].sort())
    expect(CHANNEL_TYPE_LIST).toHaveLength(ALL.length)
  })

  it('cada tipo declara cómo pedir su identificador y su icono', () => {
    for (const c of CHANNEL_TYPE_LIST) {
      expect(c.label).toBeTruthy()
      expect(c.externalIdLabel).toBeTruthy()
      expect(c.icon).toBeTruthy()
    }
  })

  it('solo Facebook e Instagram piden el token de la página (obligatorio); el resto no pide credenciales', () => {
    for (const c of CHANNEL_TYPE_LIST) {
      if (c.type === 'facebook' || c.type === 'instagram') {
        expect(c.credentials).toEqual([expect.objectContaining({ key: 'page_access_token', required: true })])
      } else {
        expect(c.credentials).toEqual([])
      }
    }
  })
})

describe('maskExternalId', () => {
  it('oculta el token de Telegram (el external_id ES el secreto del bot)', () => {
    const masked = maskExternalId('telegram', '123456789:AAFsecretoSuperLargo')
    expect(masked).toBe('123456789:••••••••')
    expect(masked).not.toContain('AAF')
  })

  it('enmascara igual un valor sin ":" (formato inesperado): nunca lo pinta entero', () => {
    const masked = maskExternalId('telegram', 'tokenSinDosPuntosMuyLargo')
    expect(masked).toBe('toke••••••••')
    expect(masked).not.toContain('SinDosPuntos')
  })

  it('deja intactos los identificadores no sensibles', () => {
    expect(maskExternalId('whatsapp_evolution', 'vital-wa')).toBe('vital-wa')
    expect(maskExternalId('instagram', '17841400000000')).toBe('17841400000000')
  })
})

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
