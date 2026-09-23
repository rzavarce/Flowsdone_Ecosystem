import { describe, expect, it, vi } from 'vitest'
import { createHttpAuthApi, parseUser } from './httpAuthApi'
import { makeUser } from '@/test/renderApp'

/** What `parseUser` returns for a user without the optional profile fields. */
const normalized = <T extends object>(u: T) => ({ phone: null, address: null, social_links: {}, avatar_updated_at: null, ...u })

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

describe('parseUser', () => {
  it('acepta un usuario válido', () => {
    const u = makeUser('admin')
    expect(parseUser(u)).toEqual(normalized(u))
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

    expect(result).toEqual(normalized(user))
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
    expect(await createHttpAuthApi('/api', vi.fn().mockResolvedValue(json(user))).restore()).toEqual(normalized(user))
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

    expect(result).toEqual(normalized(user))
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

    expect(result).toEqual(normalized(user))
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/auth/reset-password')
    expect(JSON.parse(init.body)).toEqual({ token: 'tok', password: 'x'.repeat(10) })
  })

  it('resetPassword con 400 -> invalid_token', async () => {
    const api = createHttpAuthApi('/api', vi.fn().mockResolvedValue(json({ detail: 'invalid or expired link' }, 400)))
    await expect(api.resetPassword('tok', 'x')).rejects.toMatchObject({ code: 'invalid_token', message: 'invalid or expired link' })
  })
})

describe('httpAuthApi: perfil propio', () => {
  it('parseUser conserva los datos de perfil y descarta redes desconocidas', () => {
    const u = {
      ...makeUser('client'),
      phone: '600',
      address: 'Calle 1',
      social_links: { linkedin: 'https://l.in/x', myspace: 'https://m.s', x: 42 },
      avatar_updated_at: '2026-09-23T10:00:00Z',
    }
    expect(parseUser(u)).toMatchObject({
      phone: '600',
      address: 'Calle 1',
      social_links: { linkedin: 'https://l.in/x' },
      avatar_updated_at: '2026-09-23T10:00:00Z',
    })
  })

  it('updateProfile hace PATCH /me/profile con la cabecera CSRF y devuelve el usuario', async () => {
    const user = { ...makeUser('client'), phone: '600' }
    const fetchFn = vi.fn().mockResolvedValue(json(user))
    const result = await createHttpAuthApi('/api', fetchFn).updateProfile({ phone: '600' })
    expect(result.phone).toBe('600')
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/me/profile')
    expect(init.method).toBe('PATCH')
    expect(init.headers['X-Requested-With']).toBe('fd-console')
    expect(JSON.parse(init.body)).toEqual({ phone: '600' })
  })

  it('uploadAvatar envía la imagen tal cual (PUT, Content-Type de la imagen); removeAvatar hace DELETE', async () => {
    const fetchFn = vi.fn().mockImplementation(async () => json({ ...makeUser('client'), avatar_updated_at: 'v1' }))
    const api = createHttpAuthApi('/api', fetchFn)
    const image = new Blob(['jpeg'], { type: 'image/jpeg' })
    await api.uploadAvatar(image)
    const [url, init] = fetchFn.mock.calls[0]!
    expect(url).toBe('/api/me/avatar')
    expect(init.method).toBe('PUT')
    expect(init.body).toBe(image)
    expect(init.headers['Content-Type']).toBe('image/jpeg')

    await api.removeAvatar()
    expect(fetchFn.mock.calls[1]![1].method).toBe('DELETE')
  })

  it('avatarUrl apunta a /me/avatar con la versión, o null sin foto', () => {
    const api = createHttpAuthApi('/api', vi.fn())
    expect(api.avatarUrl({ ...makeUser('client'), avatar_updated_at: '2026-09-23T10:00:00+00:00' })).toBe(
      '/api/me/avatar?v=2026-09-23T10%3A00%3A00%2B00%3A00',
    )
    expect(api.avatarUrl(makeUser('client'))).toBeNull()
  })

  it('un error del servidor llega como ApiError con su detalle', async () => {
    const fetchFn = vi.fn().mockResolvedValue(json({ detail: 'phone must contain only digits' }, 400))
    await expect(createHttpAuthApi('/api', fetchFn).updateProfile({ phone: 'x' })).rejects.toMatchObject({
      status: 400,
      message: 'phone must contain only digits',
    })
  })
})
