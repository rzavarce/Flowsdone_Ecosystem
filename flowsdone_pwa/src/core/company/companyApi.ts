import type { Statement, TenantBillingProfile } from '@/core/admin/types'

/**
 * Client for `GET /me/billing-profile` (self-service: never goes through
 * `/internal/admin/*` nor `AdminApi` - a `client` has no access to the admin
 * API whatsoever, see `access_control.py`). Same `credentials: 'include'`
 * pattern as `httpAuthApi.ts`.
 */
export interface CompanyApi {
  /** Billing data for the logged-in user's tenant; `null` if nothing has been saved yet. */
  getMyCompany(): Promise<TenantBillingProfile | null>
  /**
   * Usage and charges of the user's tenant for a month (`YYYY-MM`, current if
   * omitted) - `GET /me/usage`, never with Flowsdone's costs. `null` if the
   * account has no tenant.
   */
  getMyUsage(period?: string): Promise<Statement | null>
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
    async getMyUsage(period) {
      const qs = period ? `?period=${encodeURIComponent(period)}` : ''
      const res = await fetchFn(`${baseUrl}/me/usage${qs}`, { credentials: 'include' })
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`no se pudo cargar el consumo (${res.status})`)
      return (await res.json()) as Statement
    },
  }
}
