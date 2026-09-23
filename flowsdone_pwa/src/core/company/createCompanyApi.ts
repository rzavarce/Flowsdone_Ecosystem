import { AUTH_MODE } from '@/core/auth/createAuthApi'
import type { CompanyApi } from './companyApi'
import { createHttpCompanyApi } from './companyApi'
import { createMockCompanyApi } from './mockCompanyApi'

/** Instantiates the "my company" adapter according to {@link AUTH_MODE} (same mode as auth/admin). */
export function createCompanyApi(): CompanyApi {
  return AUTH_MODE === 'mock' ? createMockCompanyApi() : createHttpCompanyApi(import.meta.env.VITE_API_BASE_URL)
}
