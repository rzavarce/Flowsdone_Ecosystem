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

  it('activateAccount envía token+password y devuelve el usuario (auto-login)', async () => {
    const user = makeUser('client')
    const fetchFn = vi.fn().mockResolvedValue(json(user))
    const result = await createHttpAuthApi('/api', fetchFn).activateAccount('tok', 'x'.repeat(10))

    expect(result).toEqual(user)
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/auth/activate')
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' })
    expect(JSON.parse(init.body)).toEqual({ token: 'tok', password: 'x'.repeat(10) })
  })

  it('activateAccount con 400 -> invalid_token, con el detail del servidor como mensaje', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({ detail: 'invalid or expired link' }, 400)))
    await expect(api.activateAccount('tok', 'x')).rejects.toMatchObject({ code: 'invalid_token', message: 'invalid or expired link' })
  })

  it('activateAccount con 400 sin detail -> mensaje genérico', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(new Response('not json', { status: 400 })))
    await expect(api.activateAccount('tok', 'x')).rejects.toMatchObject({
      code: 'invalid_token',
      message: expect.stringMatching(/no es válido o ya venció/),
    })
  })

  it('activateAccount con 500 o red caída -> unavailable', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, 500)))
    await expect(api.activateAccount('tok', 'x')).rejects.toMatchObject({ code: 'unavailable' })
  })

  it('requestPasswordReset envía el email y resuelve sin lanzar (202)', async () => {
    const fetchFn = vi.fn().mockResolvedValue(new Response(null, { status: 202 }))
    const api = createHttpAuthApi('/api', fetchFn)
    await expect(api.requestPasswordReset('a@b.c')).resolves.toBeUndefined()

    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/auth/forgot-password')
    expect(JSON.parse(init.body)).toEqual({ email: 'a@b.c' })
  })

  it('requestPasswordReset con 429 -> rate_limited', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({}, 429)))
    await expect(api.requestPasswordReset('a@b.c')).rejects.toMatchObject({ code: 'rate_limited' })
  })

  it('resetPassword envía token+password y devuelve el usuario (auto-login)', async () => {
    const user = makeUser('admin')
    const fetchFn = vi.fn().mockResolvedValue(json(user))
    const result = await createHttpAuthApi('/api', fetchFn).resetPassword('tok', 'x'.repeat(10))

    expect(result).toEqual(user)
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/auth/reset-password')
    expect(JSON.parse(init.body)).toEqual({ token: 'tok', password: 'x'.repeat(10) })
  })

  it('resetPassword con 400 -> invalid_token', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({ detail: 'invalid or expired link' }, 400)))
    await expect(api.resetPassword('tok', 'x')).rejects.toMatchObject({ code: 'invalid_token', message: 'invalid or expired link' })
  })
})
