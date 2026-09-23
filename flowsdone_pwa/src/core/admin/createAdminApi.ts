import { AUTH_MODE } from '@/core/auth/createAuthApi'
import type { AdminApi } from './AdminApi'
import { createHttpAdminApi } from './httpAdminApi'
import { createMockAdminApi } from './mockAdminApi'

/**
 * Instantiates the admin API adapter. Follows the same mode as
 * authentication: `mock` means no backend, `http` means the gateway is used.
 */
export function createAdminApi(): AdminApi {
  return AUTH_MODE === 'mock' ? createMockAdminApi() : createHttpAdminApi(undefined, import.meta.env.VITE_API_BASE_URL)
}
