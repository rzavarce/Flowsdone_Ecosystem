import type { TenantBillingProfile } from '@/core/admin/types'

/**
 * Cliente para `GET /me/billing-profile` (autoservicio: nunca pasa por
 * `/internal/admin/*` ni por `AdminApi` - un `client` no tiene acceso al
 * admin API en absoluto, ver `access_control.py`). Mismo patrón de
 * `credentials: 'include'` que `httpAuthApi.ts`.
 */
export interface CompanyApi {
  /** Datos de facturación del tenant del usuario logueado; `null` si todavía no se cargó nada. */
  getMyCompany(): Promise<TenantBillingProfile | null>
}

/** Crea el adaptador HTTP. `fetchFn` es inyectable para tests. */
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
