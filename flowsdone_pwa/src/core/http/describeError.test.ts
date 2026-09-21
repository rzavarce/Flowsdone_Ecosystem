import { describe, expect, it } from 'vitest'
import { ApiError } from '@/core/http/apiFetch'
import { describeError } from './describeError'

describe('describeError', () => {
  it.each([
    [403, /no tiene permiso/],
    [404, /ya no existe/],
    [409, /Ya existe/],
  ])('traduce el %i a un mensaje claro', (status, pattern) => {
    expect(describeError(new ApiError(status, 'x'))).toMatch(pattern)
  })

  it('en un 502 explica que la plataforma rechazó el registro, sin el prefijo técnico', () => {
    const message = describeError(new ApiError(502, 'webhook registration failed: Unauthorized'))
    expect(message).toContain('rechazó el registro')
    expect(message).toContain('Unauthorized')
    expect(message).not.toContain('webhook registration failed')
  })

  it('sin conexión (status 0) conserva el mensaje de red', () => {
    expect(describeError(new ApiError(0, 'No se pudo contactar con el servidor.'))).toBe('No se pudo contactar con el servidor.')
  })

  it('otros errores del gateway muestran su detalle; los no-API, su mensaje', () => {
    expect(describeError(new ApiError(400, 'agent does not belong to the project'))).toBe('agent does not belong to the project')
    expect(describeError(new Error('boom'))).toBe('boom')
    expect(describeError('raro')).toBe('Ocurrió un error inesperado.')
  })
})
