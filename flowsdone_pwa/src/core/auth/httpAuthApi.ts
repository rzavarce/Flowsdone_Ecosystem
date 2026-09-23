import { AuthError, type AuthApi } from './AuthApi'
import { ROLES, type Role, type Tenant, type User } from './types'

/**
 * Adaptador contra el gateway real (api_gateway, `/auth/*`, servido bajo `/api`
 * por nginx en el contenedor o por el proxy de Vite en desarrollo). Contrato:
 *
 * - `POST {base}/auth/login`            body `{email, password}` -> 200 `User` | 401 | 429
 * - `GET  {base}/auth/me`                -> 200 `User` | 401
 * - `POST {base}/auth/logout`            -> 204
 * - `POST {base}/auth/activate`          body `{token, password}` -> 200 `User` | 400
 * - `POST {base}/auth/forgot-password`   body `{email}`           -> 202 | 429
 * - `POST {base}/auth/reset-password`    body `{token, password}` -> 200 `User` | 400
 *
 * La sesión viaja en una cookie httpOnly (`credentials: 'include'`): el
 * frontend nunca ve ni guarda el token, lo que lo deja fuera del alcance de XSS.
 * Lo mismo aplica al token de activación/reset: solo viaja en la URL del link
 * (nunca en una cookie ni en localStorage) y el servidor lo consume una sola vez.
 */

const UNAVAILABLE = 'No se pudo contactar con el servidor. Inténtalo de nuevo.'
const RATE_LIMITED = 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.'
const INVALID_TOKEN_FALLBACK = 'El enlace no es válido o ya venció. Pide uno nuevo.'

/** Extrae el `detail` de un cuerpo de error de FastAPI, si lo hay. */
async function detailOf(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : undefined
  } catch {
    return undefined
  }
}

function isTenant(value: unknown): value is Tenant {
  const t = value as Tenant
  return !!t && typeof t.id === 'string' && typeof t.name === 'string'
}

/**
 * Valida la forma de un `User` recibido del servidor.
 *
 * @param data - JSON sin confiar.
 * @returns El usuario tipado.
 * @throws AuthError `unavailable` si la respuesta no tiene la forma esperada.
 */
export function parseUser(data: unknown): User {
  const u = data as Partial<User> | null
  if (
    !u ||
    typeof u.id !== 'string' ||
    typeof u.name !== 'string' ||
    typeof u.email !== 'string' ||
    !ROLES.includes(u.role as Role) ||
    !Array.isArray(u.tenants) ||
    !u.tenants.every(isTenant)
  ) {
    throw new AuthError('unavailable', UNAVAILABLE)
  }
  return u as User
}

/** Crea el adaptador HTTP. `fetchFn` es inyectable para tests. */
export function createHttpAuthApi(baseUrl = '/api', fetchFn: typeof fetch = (...args) => fetch(...args)): AuthApi {
  // X-Requested-With: el gateway lo exige en toda petición que cambia datos y va con
  // cookie (defensa CSRF); un origen ajeno no puede enviarlo sin permiso CORS.
  const request = (path: string, init?: RequestInit) =>
    fetchFn(`${baseUrl}${path}`, {
      credentials: 'include',
      ...init,
      headers: { 'X-Requested-With': 'fd-console', ...init?.headers },
    })

  return {
    async restore() {
      try {
        const res = await request('/auth/me')
        return res.ok ? parseUser(await res.json()) : null
      } catch {
        // Servidor caído o respuesta inválida al abrir: tratamos como sin sesión.
        return null
      }
    },

    async login(credentials) {
      let res: Response
      try {
        res = await request('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(credentials),
        })
      } catch {
        throw new AuthError('unavailable', UNAVAILABLE)
      }
      if (res.status === 400 || res.status === 401) {
        throw new AuthError('invalid_credentials', 'Correo o contraseña incorrectos.')
      }
      if (res.status === 429) {
        throw new AuthError('rate_limited', 'Demasiados intentos. Espera unos minutos e inténtalo de nuevo.')
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE)
      return parseUser(await res.json())
    },

    async logout() {
      try {
        await request('/auth/logout', { method: 'POST' })
      } catch {
        // Mejor esfuerzo: la UI cierra la sesión local igualmente.
      }
    },

    async activateAccount(token, password) {
      let res: Response
      try {
        res = await request('/auth/activate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, password }),
        })
      } catch {
        throw new AuthError('unavailable', UNAVAILABLE)
      }
      if (res.status === 400) {
        throw new AuthError('invalid_token', (await detailOf(res)) ?? INVALID_TOKEN_FALLBACK)
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE)
      return parseUser(await res.json())
    },

    async requestPasswordReset(email) {
      let res: Response
      try {
        res = await request('/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        })
      } catch {
        throw new AuthError('unavailable', UNAVAILABLE)
      }
      if (res.status === 429) {
        throw new AuthError('rate_limited', RATE_LIMITED)
      }
      // Cualquier otra respuesta (incluida un correo desconocido) se trata
      // como éxito a propósito: el backend nunca revela si la cuenta existe.
      if (res.status !== 202 && !res.ok) throw new AuthError('unavailable', UNAVAILABLE)
    },

    async resetPassword(token, password) {
      let res: Response
      try {
        res = await request('/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, password }),
        })
      } catch {
        throw new AuthError('unavailable', UNAVAILABLE)
      }
      if (res.status === 400) {
        throw new AuthError('invalid_token', (await detailOf(res)) ?? INVALID_TOKEN_FALLBACK)
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE)
      return parseUser(await res.json())
    },
  }
}
