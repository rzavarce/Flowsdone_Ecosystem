import { describe, expect, it } from 'vitest'
import { contactLabel, identifierLabel } from './labels'

describe('identifierLabel / contactLabel', () => {
  it('las llamadas del softphone de la demo se muestran legibles', () => {
    expect(identifierLabel('client:demo-4k2m9x7q')).toBe('Llamada desde el navegador · demo-4k2m9x7q')
    expect(identifierLabel('+34 600 111 222')).toBe('+34 600 111 222')
    expect(identifierLabel('34600111222@s.whatsapp.net')).toBe('+34600111222')
    expect(identifierLabel('120363041234567890@g.us')).toBe('120363041234567890@g.us')
  })

  it('el nombre de la ficha tiene prioridad sobre el identificador', () => {
    expect(contactLabel({ contact: 'client:demo-4k2m9x7q', contact_name: 'Ana Pérez' })).toBe('Ana Pérez')
    expect(contactLabel({ contact: '@usuario11', contact_name: null })).toBe('@usuario11')
  })
})
