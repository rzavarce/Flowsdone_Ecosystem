import { AuthError, type AuthApi } from './AuthApi'
import { apiFetch } from '@/core/http/apiFetch'
import { i18n } from '@/core/i18n/i18n'
import { ROLES, SOCIAL_NETWORKS, type Role, type SocialNetwork, type Tenant, type User } from './types'

/**
 * Adapter against the real gateway (api_gateway, `/auth/*`, served under `/api`
 * by nginx in the container or by the Vite proxy in development). Contract:
 *
 * - `POST {base}/auth/login`            body `{email, password}` -> 200 `User` | 401 | 429
 * - `GET  {base}/auth/me`                -> 200 `User` | 401
 * - `POST {base}/auth/logout`            -> 204
 * - `POST {base}/auth/activate`          body `{token, password}` -> 200 `User` | 400
 * - `POST {base}/auth/forgot-password`   body `{email}`           -> 202 | 429
 * - `POST {base}/auth/reset-password`    body `{token, password}` -> 200 `User` | 400
 * - `PATCH {base}/me/profile`            body `ProfileUpdate`     -> 200 `User` | 400
 * - `PUT|DELETE {base}/me/avatar`        raw image body           -> 200 `User` | 400 | 413
 * - `GET  {base}/me/avatar?v=…`          -> the image (long private cache: the `v` changes with it)
 *
 * The session travels in an httpOnly cookie (`credentials: 'include'`): the
 * frontend never sees or stores the token, which keeps it out of XSS's reach.
 * The same applies to the activation/reset token: it only ever travels in the
 * link's URL (never in a cookie or localStorage) and the server consumes it once.
 */

// Mensajes resueltos al lanzar el error, en el idioma activo en ese momento.
const UNAVAILABLE = () => i18n.t('auth.errors.unavailable')
const RATE_LIMITED = () => i18n.t('auth.errors.rateLimited')
const INVALID_TOKEN_FALLBACK = () => i18n.t('auth.errors.invalidToken')

/** Extracts the `detail` field from a FastAPI error body, if present. */
async function detailOf(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : undefined
  } catch {
    return undefined
  }
}

/** Type guard checking whether a value has the shape of a {@link Tenant}. */
function isTenant(value: unknown): value is Tenant {
  const t = value as Tenant
  return !!t && typeof t.id === 'string' && typeof t.name === 'string'
}

/**
 * Validates the shape of a `User` received from the server.
 *
 * @param data - Untrusted JSON.
 * @returns The typed user.
 * @throws AuthError `unavailable` if the response doesn't have the expected shape.
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
    throw new AuthError('unavailable', UNAVAILABLE())
  }
  const links = (u.social_links ?? {}) as Record<string, unknown>
  return {
    ...(u as User),
    phone: typeof u.phone === 'string' ? u.phone : null,
    address: typeof u.address === 'string' ? u.address : null,
    // Solo las redes conocidas y con URL de texto (tolerante con respuestas viejas o raras).
    social_links: Object.fromEntries(
      SOCIAL_NETWORKS.filter((n) => typeof links[n] === 'string').map((n) => [n, links[n] as string]),
    ) as Partial<Record<SocialNetwork, string>>,
    avatar_updated_at: typeof u.avatar_updated_at === 'string' ? u.avatar_updated_at : null,
  }
}

/** Creates the HTTP adapter. `fetchFn` is injectable for tests. */
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
        throw new AuthError('unavailable', UNAVAILABLE())
      }
      if (res.status === 400 || res.status === 401) {
        throw new AuthError('invalid_credentials', i18n.t('auth.errors.invalidCredentials'))
      }
      if (res.status === 429) {
        throw new AuthError('rate_limited', RATE_LIMITED())
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE())
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
        throw new AuthError('unavailable', UNAVAILABLE())
      }
      if (res.status === 400) {
        throw new AuthError('invalid_token', (await detailOf(res)) ?? INVALID_TOKEN_FALLBACK())
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE())
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
        throw new AuthError('unavailable', UNAVAILABLE())
      }
      if (res.status === 429) {
        throw new AuthError('rate_limited', RATE_LIMITED())
      }
      // Cualquier otra respuesta (incluida un correo desconocido) se trata
      // como éxito a propósito: el backend nunca revela si la cuenta existe.
      if (res.status !== 202 && !res.ok) throw new AuthError('unavailable', UNAVAILABLE())
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
        throw new AuthError('unavailable', UNAVAILABLE())
      }
      if (res.status === 400) {
        throw new AuthError('invalid_token', (await detailOf(res)) ?? INVALID_TOKEN_FALLBACK())
      }
      if (!res.ok) throw new AuthError('unavailable', UNAVAILABLE())
      return parseUser(await res.json())
    },
    async updateProfile(patch) {
      return parseUser(await apiFetch('/me/profile', { method: 'PATCH', body: patch, fetchFn, baseUrl }))
    },
    async uploadAvatar(image) {
      return parseUser(await apiFetch('/me/avatar', { method: 'PUT', blob: image, fetchFn, baseUrl }))
    },
    async removeAvatar() {
      return parseUser(await apiFetch('/me/avatar', { method: 'DELETE', fetchFn, baseUrl }))
    },
    avatarUrl(user) {
      return user.avatar_updated_at ? `${baseUrl}/me/avatar?v=${encodeURIComponent(user.avatar_updated_at)}` : null
    },
  }
}
