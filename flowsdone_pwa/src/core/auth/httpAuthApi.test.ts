import { describe, expect, it, vi } from 'vitest'
import { createHttpAuthApi, parseUser } from './httpAuthApi'
import { makeUser } from '@/test/renderApp'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

describe('parseUser', () => {
  it('acepta un usuario válido', () => {
    const u = makeUser('admin')
    expect(parseUser(u)).toEqual(u)
  })

  it.each([
    ['null', null],
    ['rol desconocido', { ...makeUser('admin'), role: 'root' }],
    ['sin tenants', { ...makeUser('admin'), tenants: undefined }],
    ['tenant mal formado', { ...makeUser('admin'), tenants: [{ id: 1 }] }],
  ])('rechaza %s', (_, data) => {
    expect(() => parseUser(data)).toThrow()
  })
})

describe('httpAuthApi', () => {
  it('login envía credenciales con cookie de sesión y devuelve el usuario', async () => {
    const user = makeUser('botmaster')
    const fetchFn = vi.fn().mockResolvedValue(json(user))
    const result = await createHttpAuthApi('/api', fetchFn).login({ email: 'a@b.c', password: 'x' })

    expect(result).toEqual(user)
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/auth/login')
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' })
    expect(init.headers).toMatchObject({ 'X-Requested-With': 'fd-console', 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ email: 'a@b.c', password: 'x' })
  })

  it.each([400, 401])('login con %i -> invalid_credentials', async (status) => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, status)))
    await expect(api.login({ email: 'a', password: 'b' })).rejects.toMatchObject({ code: 'invalid_credentials' })
  })

  it('login con 429 -> rate_limited (demasiados intentos)', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, 429)))
    await expect(api.login({ email: 'a', password: 'b' })).rejects.toMatchObject({
      code: 'rate_limited',
      message: expect.stringMatching(/Demasiados intentos/),
    })
  })

  it('login con 500 o red caída -> unavailable', async () => {
    const bad = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, 500)))
    await expect(bad.login({ email: 'a', password: 'b' })).rejects.toMatchObject({ code: 'unavailable' })
    const down = createHttpAuthApi('/api', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    await expect(down.login({ email: 'a', password: 'b' })).rejects.toMatchObject({ code: 'unavailable' })
  })

  it('restore devuelve el usuario, o null si 401 / servidor caído', async () => {
    const user = makeUser('client')
    expect(await createHttpAuthApi('/api', vi.fn().mockResolvedValue(json(user))).restore()).toEqual(user)
    expect(await createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, 401))).restore()).toBeNull()
    expect(await createHttpAuthApi('/api', vi.fn().mockRejectedValue(new Error('x'))).restore()).toBeNull()
  })

  it('logout no lanza aunque falle la red', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockRejectedValue(new Error('x')))
    await expect(api.logout()).resolves.toBeUndefined()
  })
})
