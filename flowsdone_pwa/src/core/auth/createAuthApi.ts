import type { AuthApi } from './AuthApi'
import { createHttpAuthApi } from './httpAuthApi'
import { createMockAuthApi } from './mockAuthApi'

/**
 * Modo de autenticación. Por defecto `mock` en desarrollo y `http` en un
 * build de producción, de modo que las cuentas de demostración no lleguen al
 * VPS por accidente. Se fuerza con `VITE_AUTH_MODE` (`mock` | `http`).
 */
export const AUTH_MODE: 'mock' | 'http' =
  import.meta.env.VITE_AUTH_MODE === 'mock' || import.meta.env.VITE_AUTH_MODE === 'http'
    ? import.meta.env.VITE_AUTH_MODE
    : import.meta.env.DEV
      ? 'mock'
      : 'http'

/** Instancia el adaptador según {@link AUTH_MODE}. */
export function createAuthApi(): AuthApi {
  return AUTH_MODE === 'mock' ? createMockAuthApi() : createHttpAuthApi(import.meta.env.VITE_API_BASE_URL)
}
