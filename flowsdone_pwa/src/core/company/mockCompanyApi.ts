import type { TenantBillingProfile } from '@/core/admin/types'
import type { CompanyApi } from './companyApi'

const NOW = '2026-09-01T10:00:00Z'

/** Demo profile, consistent with "Clínica Vital" (the first tenant in `mockAdminApi.ts`). */
const MOCK_PROFILE: TenantBillingProfile = {
  id: 'bp-mock',
  tenant_id: 't-vital',
  legal_name: 'Clínica Vital S.A. de C.V.',
  tax_id: 'CVI010203AB4',
  billing_email: 'facturas@clinicavital.com',
  billing_contact_name: 'Carla Cliente',
  billing_phone: '+52 55 1234 5678',
  address_line1: 'Av. Reforma 123',
  address_line2: 'Piso 4',
  city: 'Ciudad de México',
  state_province: 'CDMX',
  postal_code: '06600',
  country: 'México',
  currency: 'MXN',
  plan: 'pro',
  billing_cycle: 'mensual',
  notes: null,
  created_at: NOW,
  updated_at: NOW,
}

/** MOCK adapter: always returns the same profile, with no backend. */
export function createMockCompanyApi({ latencyMs = 250 }: { latencyMs?: number } = {}): CompanyApi {
  return {
    async getMyCompany() {
      await new Promise<void>((resolve) => setTimeout(resolve, latencyMs))
      return { ...MOCK_PROFILE }
    },
  }
}
