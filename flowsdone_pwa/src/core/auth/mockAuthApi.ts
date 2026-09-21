import { AuthError, type AuthApi } from './AuthApi'
import type { Role, Tenant, User } from './types'

/**
 * Adaptador de MAQUETA: cuentas de demostración en memoria, sin backend.
 * Nunca debe usarse en producción; ver `createAuthApi`.
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

/** Cuentas que la pantalla de login ofrece para rellenar el formulario. */
export const DEMO_ACCOUNTS: readonly { email: string; password: string; role: Role; name: string }[] = USERS.map(
  (u) => ({ email: u.email, password: DEMO_PASSWORD, role: u.role, name: u.name }),
)

export const MOCK_SESSION_KEY = 'fd-mock-session'

/** Opciones de {@link createMockAuthApi}. */
export interface MockAuthOptions {
  /** Latencia simulada por llamada, en ms. */
  latencyMs?: number
  /** Storage donde se recuerda la sesión (guarda solo el id de usuario). */
  storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null
}

function defaultStorage(): MockAuthOptions['storage'] {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** Crea el adaptador mock. */
export function createMockAuthApi({ latencyMs = 350, storage = defaultStorage() }: MockAuthOptions = {}): AuthApi {
  const wait = () => new Promise<void>((resolve) => setTimeout(resolve, latencyMs))
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
        throw new AuthError('invalid_credentials', 'Correo o contraseña incorrectos.')
      }
      remember(() => storage?.setItem(MOCK_SESSION_KEY, user.id))
      return user
    },

    async logout() {
      remember(() => storage?.removeItem(MOCK_SESSION_KEY))
    },
  }
}
