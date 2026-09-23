import type { TenantBillingProfile } from '@/core/admin/types'

/**
 * Client for `GET /me/billing-profile` (self-service: never goes through
 * `/internal/admin/*` nor `AdminApi` - a `client` has no access to the admin
 * API whatsoever, see `access_control.py`). Same `credentials: 'include'`
 * pattern as `httpAuthApi.ts`.
 */
export interface CompanyApi {
  /** Billing data for the logged-in user's tenant; `null` if nothing has been saved yet. */
  getMyCompany(): Promise<TenantBillingProfile | null>
}

/** Creates the HTTP adapter. `fetchFn` is injectable for tests. */
export function createHttpCompanyApi(baseUrl = '/api', fetchFn: typeof fetch = (...args) => fetch(...args)): CompanyApi {
  return {
    async getMyCompany() {
      const res = await fetchFn(`${baseUrl}/me/billing-profile`, { credentials: 'include' })
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`no se pudo cargar la empresa (${res.status})`)
      return (await res.json()) as TenantBillingProfile
    },
  }
}
