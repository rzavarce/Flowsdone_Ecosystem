import { AUTH_MODE } from '@/core/auth/createAuthApi'
import type { CompanyApi } from './companyApi'
import { createHttpCompanyApi } from './companyApi'
import { createMockCompanyApi } from './mockCompanyApi'

/** Instancia el adaptador de "mi empresa" según {@link AUTH_MODE} (mismo modo que auth/admin). */
export function createCompanyApi(): CompanyApi {
  return AUTH_MODE === 'mock' ? createMockCompanyApi() : createHttpCompanyApi(import.meta.env.VITE_API_BASE_URL)
}
