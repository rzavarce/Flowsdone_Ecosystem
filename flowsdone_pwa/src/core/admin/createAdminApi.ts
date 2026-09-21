import { AUTH_MODE } from '@/core/auth/createAuthApi'
import type { AdminApi } from './AdminApi'
import { createHttpAdminApi } from './httpAdminApi'
import { createMockAdminApi } from './mockAdminApi'

/**
 * Instancia el adaptador de la API admin. Sigue el mismo modo que la
 * autenticación: con `mock` no hay backend, con `http` se usa el gateway.
 */
export function createAdminApi(): AdminApi {
  return AUTH_MODE === 'mock' ? createMockAdminApi() : createHttpAdminApi(undefined, import.meta.env.VITE_API_BASE_URL)
}
