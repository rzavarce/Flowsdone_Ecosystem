import { describe, expect, it, vi } from 'vitest'
import { ApiError, CSRF_HEADERS, apiFetch } from './apiFetch'

const res = (body: unknown, status = 200) => new Response(body === undefined ? null : JSON.stringify(body), { status })

describe('apiFetch', () => {
  it('envía cookie, cabecera anti-CSRF y el cuerpo como JSON', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res({ ok: true }))
    await apiFetch('/admin/projects', { method: 'POST', body: { name: 'x' }, fetchFn })

    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/admin/projects')
    expect(init.credentials).toBe('include')
    expect(init.headers).toMatchObject({ ...CSRF_HEADERS, 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ name: 'x' })
  })

  it('un GET no manda Content-Type ni cuerpo', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res([]))
    await apiFetch('/admin/projects', { fetchFn })
    const [, init] = fetchFn.mock.calls[0]!
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
    expect(init.headers).not.toHaveProperty('Content-Type')
  })

  it('respeta la base configurada', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res([]))
    await apiFetch('/x', { fetchFn, baseUrl: 'https://api.test' })
    expect(fetchFn.mock.calls[0]![0]).toBe('https://api.test/x')
  })

  it('devuelve el JSON tipado y undefined en un 204', async () => {
    expect(await apiFetch('/x', { fetchFn: vi.fn().mockResolvedValue(res({ a: 1 })) })).toEqual({ a: 1 })
    expect(await apiFetch('/x', { fetchFn: vi.fn().mockResolvedValue(new Response(null, { status: 204 })) })).toBeUndefined()
  })

  it('un error usa el detail de FastAPI como mensaje y conserva el estado', async () => {
    const err = await apiFetch('/x', { fetchFn: vi.fn().mockResolvedValue(res({ detail: 'project not found' }, 404)) }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 404, message: 'project not found' })
  })

  it('resume los errores de validación (422)', async () => {
    const detail = [{ loc: ['body', 'email'], msg: 'field required' }, { loc: ['body', 'name'], msg: 'too short' }]
    const err = await apiFetch('/x', { fetchFn: vi.fn().mockResolvedValue(res({ detail }, 422)) }).catch((e) => e)
    expect((err as ApiError).message).toBe('email: field required; name: too short')
  })

  it('un error sin cuerpo JSON cae en un mensaje genérico con el código', async () => {
    const err = await apiFetch('/x', { fetchFn: vi.fn().mockResolvedValue(new Response('<html>', { status: 502 })) }).catch((e) => e)
    expect(err).toMatchObject({ status: 502, message: 'Error 502' })
  })

  it('si no hay conexión lanza ApiError con status 0', async () => {
    const err = await apiFetch('/x', { fetchFn: vi.fn().mockRejectedValue(new TypeError('fetch failed')) }).catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(0)
  })
})
