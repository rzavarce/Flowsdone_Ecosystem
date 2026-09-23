import type { AuthApi } from './AuthApi'
import { createHttpAuthApi } from './httpAuthApi'
import { createMockAuthApi } from './mockAuthApi'

/**
 * Authentication mode. Defaults to `mock` in development and `http` in a
 * production build, so demo accounts never reach the VPS by accident.
 * Overridden with `VITE_AUTH_MODE` (`mock` | `http`).
 */
export const AUTH_MODE: 'mock' | 'http' =
  import.meta.env.VITE_AUTH_MODE === 'mock' || import.meta.env.VITE_AUTH_MODE === 'http'
    ? import.meta.env.VITE_AUTH_MODE
    : import.meta.env.DEV
      ? 'mock'
      : 'http'

/** Instantiates the adapter according to {@link AUTH_MODE}. */
export function createAuthApi(): AuthApi {
  return AUTH_MODE === 'mock' ? createMockAuthApi() : createHttpAuthApi(import.meta.env.VITE_API_BASE_URL)
}
