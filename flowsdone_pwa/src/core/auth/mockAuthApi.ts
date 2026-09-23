import { AuthError, type AuthApi } from './AuthApi'
import { ApiError } from '@/core/http/apiFetch'
import { i18n } from '@/core/i18n/i18n'
import type { Role, Tenant, User } from './types'

/**
 * MOCK adapter: in-memory demo accounts, with no backend.
 * Must never be used in production; see `createAuthApi`.
 */

const TENANTS: Tenant[] = [
  { id: 't-vital', name: 'Clínica Vital' },
  { id: 't-norte', name: 'Inmobiliaria Norte' },
  { id: 't-aurora', name: 'Tienda Aurora' },
  { id: 't-fibra', name: 'Fibra Hogar' },
]

const DEMO_PASSWORD = 'demo1234'

const USERS: User[] = [
  { id: 'u-admin', name: 'Ana Administradora', email: 'admin@flowsdone.dev', role: 'admin', tenants: TENANTS },
  { id: 'u-manager', name: 'Marcos Gestor', email: 'gestor@flowsdone.dev', role: 'tenant_manager', tenants: TENANTS.slice(0, 2) },
  { id: 'u-botmaster', name: 'Bea Botmaster', email: 'botmaster@flowsdone.dev', role: 'botmaster', tenants: TENANTS.slice(0, 3) },
  { id: 'u-client', name: 'Carla Cliente', email: 'cliente@flowsdone.dev', role: 'client', tenants: TENANTS.slice(0, 1) },
]

/** Accounts the login screen offers to auto-fill the form. */
export const DEMO_ACCOUNTS: readonly { email: string; password: string; role: Role; name: string }[] = USERS.map(
  (u) => ({ email: u.email, password: DEMO_PASSWORD, role: u.role, name: u.name }),
)

/** Storage key under which the mock session (a user id) is remembered. */
export const MOCK_SESSION_KEY = 'fd-mock-session'

/** Demo tokens for exercising `/activate-account/:token` and `/reset-password/:token`
 * in mock mode with no backend; any other value is rejected as invalid/expired. */
export const DEMO_ACTIVATION_TOKEN = 'demo-activate-token'
/** Demo token for exercising `/reset-password/:token` in mock mode; see {@link DEMO_ACTIVATION_TOKEN}. */
export const DEMO_RESET_TOKEN = 'demo-reset-token'
const INVALID_TOKEN = () => i18n.t('auth.errors.invalidToken')

/** Photos of the demo accounts (data URLs), in memory only. */
const AVATARS = new Map<string, string>()

/** Reads a blob as a data URL (the mock has no server to serve the photo from). */
function toDataUrl(image: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(image)
  })
}

/** Options for {@link createMockAuthApi}. */
export interface MockAuthOptions {
  /** Simulated latency per call, in ms. */
  latencyMs?: number
  /** Storage where the session is remembered (stores only the user id). */
  storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null
}

/** Resolves the default session storage, falling back to `null` if `localStorage` is unavailable. */
function defaultStorage(): MockAuthOptions['storage'] {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** Creates the mock adapter. */
export function createMockAuthApi({ latencyMs = 350, storage = defaultStorage() }: MockAuthOptions = {}): AuthApi {
  const wait = () => new Promise<void>((resolve) => setTimeout(resolve, latencyMs))
  /** The signed-in demo user (the one stored in the mock session). */
  const current = () => {
    const id = storage?.getItem(MOCK_SESSION_KEY)
    const user = USERS.find((u) => u.id === id)
    if (!user) throw new ApiError(401, 'not authenticated')
    return user
  }
  const remember = (fn: () => void) => {
    try {
      fn()
    } catch {
      // Sin storage la sesión vale solo hasta recargar.
    }
  }

  return {
    async restore() {
      await wait()
      try {
        const id = storage?.getItem(MOCK_SESSION_KEY)
        return USERS.find((u) => u.id === id) ?? null
      } catch {
        return null
      }
    },

    async login({ email, password }) {
      await wait()
      const user = USERS.find((u) => u.email === email.trim().toLowerCase())
      if (!user || password !== DEMO_PASSWORD) {
        throw new AuthError('invalid_credentials', i18n.t('auth.errors.invalidCredentials'))
      }
      remember(() => storage?.setItem(MOCK_SESSION_KEY, user.id))
      return user
    },

    async logout() {
      remember(() => storage?.removeItem(MOCK_SESSION_KEY))
    },

    async activateAccount(token, password) {
      await wait()
      if (token !== DEMO_ACTIVATION_TOKEN || password.length < 10) {
        throw new AuthError('invalid_token', INVALID_TOKEN())
      }
      const user = USERS[0]
      remember(() => storage?.setItem(MOCK_SESSION_KEY, user.id))
      return user
    },

    async requestPasswordReset() {
      await wait()
      // Siempre "éxito", exista o no la cuenta - mismo comportamiento que el adaptador real.
    },

    async resetPassword(token, password) {
      await wait()
      if (token !== DEMO_RESET_TOKEN || password.length < 10) {
        throw new AuthError('invalid_token', INVALID_TOKEN())
      }
      const user = USERS[0]
      remember(() => storage?.setItem(MOCK_SESSION_KEY, user.id))
      return user
    },
    async updateProfile(patch) {
      await wait()
      const user = current()
      if (patch.name !== undefined) user.name = patch.name.trim()
      if (patch.phone !== undefined) user.phone = patch.phone.trim() || null
      if (patch.address !== undefined) user.address = patch.address.trim() || null
      if (patch.social_links !== undefined) {
        user.social_links = Object.fromEntries(Object.entries(patch.social_links).filter(([, url]) => url?.trim()))
      }
      return { ...user }
    },
    async uploadAvatar(image) {
      await wait()
      const user = current()
      AVATARS.set(user.id, await toDataUrl(image))
      user.avatar_updated_at = new Date().toISOString()
      return { ...user }
    },
    async removeAvatar() {
      await wait()
      const user = current()
      AVATARS.delete(user.id)
      user.avatar_updated_at = null
      return { ...user }
    },
    avatarUrl(user) {
      return AVATARS.get(user.id) ?? null
    },
  }
}
