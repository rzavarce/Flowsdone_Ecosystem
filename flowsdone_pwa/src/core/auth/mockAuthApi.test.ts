import { beforeEach, describe, expect, it } from 'vitest'
import { AuthError } from './AuthApi'
import { DEMO_ACCOUNTS, MOCK_SESSION_KEY, createMockAuthApi } from './mockAuthApi'

const memoryStorage = () => {
  const data = new Map<string, string>()
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
    data,
  }
}

describe('mockAuthApi', () => {
  let storage: ReturnType<typeof memoryStorage>
  beforeEach(() => {
    storage = memoryStorage()
  })
  const make = () => createMockAuthApi({ latencyMs: 0, storage })

  it('ofrece una cuenta por cada perfil', () => {
    expect(DEMO_ACCOUNTS.map((a) => a.role).sort()).toEqual(['admin', 'botmaster', 'client', 'tenant_manager'])
  })

  it('inicia sesión con cada cuenta demo y devuelve el rol correcto', async () => {
    for (const acc of DEMO_ACCOUNTS) {
      const user = await make().login({ email: acc.email, password: acc.password })
      expect(user.role).toBe(acc.role)
    }
  })

  it('ignora mayúsculas y espacios del correo', async () => {
    const user = await make().login({ email: '  ADMIN@flowsdone.dev ', password: 'demo1234' })
    expect(user.role).toBe('admin')
  })

  it('rechaza contraseña incorrecta o correo desconocido con invalid_credentials', async () => {
    for (const creds of [
      { email: 'admin@flowsdone.dev', password: 'mala' },
      { email: 'nadie@flowsdone.dev', password: 'demo1234' },
    ]) {
      await expect(make().login(creds)).rejects.toMatchObject({ code: 'invalid_credentials' })
      await expect(make().login(creds)).rejects.toBeInstanceOf(AuthError)
    }
  })

  it('recuerda la sesión (solo el id, nunca la contraseña) y la restaura', async () => {
    await make().login({ email: 'cliente@flowsdone.dev', password: 'demo1234' })
    expect(storage.data.get(MOCK_SESSION_KEY)).toBe('u-client')
    expect(JSON.stringify([...storage.data.values()])).not.toContain('demo1234')
    expect((await make().restore())?.role).toBe('client')
  })

  it('logout borra la sesión', async () => {
    const api = make()
    await api.login({ email: 'admin@flowsdone.dev', password: 'demo1234' })
    await api.logout()
    expect(await api.restore()).toBeNull()
  })

  it('restore sin sesión devuelve null', async () => {
    expect(await make().restore()).toBeNull()
  })
})
