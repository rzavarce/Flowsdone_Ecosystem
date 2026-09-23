import type { Statement, TenantBillingProfile } from '@/core/admin/types'
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

/** Demo month for "Clínica Vital" on the Pro plan (no costs: clients never see them). */
const mockUsage = (period: string): Statement => ({
  tenant_id: 't-vital',
  period,
  status: 'preview',
  currency: 'EUR',
  plan_id: 'plan-pro',
  plan_code: 'pro',
  plan_name: 'Pro',
  overage_mode: 'overage',
  monthly_fee_micros: 99_000_000,
  channels: [
    { channel_type: 'whatsapp_evolution', messages: 3240, included: 3000, overage_messages: 240, overage_price_micros: 20_000, overage_amount_micros: 4_800_000, cost_micros: null },
    { channel_type: 'telegram', messages: 410, included: 1000, overage_messages: 0, overage_price_micros: 25_000, overage_amount_micros: 0, cost_micros: null },
  ],
  costs: null,
  overage_amount_micros: 4_800_000,
  revenue_micros: 103_800_000,
  cost_micros: null,
  margin_micros: null,
  margin_pct: null,
  llm_input_tokens: 2_044_000,
  llm_output_tokens: 219_000,
  llm_cached_input_tokens: 0,
  token_allowance: null,
  over_token_allowance: false,
  disallowed_models: [],
  unrated_meters: null,
  generated_at: NOW,
})

/** MOCK adapter: always returns the same profile, with no backend. */
export function createMockCompanyApi({ latencyMs = 250 }: { latencyMs?: number } = {}): CompanyApi {
  return {
    async getMyCompany() {
      await new Promise<void>((resolve) => setTimeout(resolve, latencyMs))
      return { ...MOCK_PROFILE }
    },
    async getMyUsage(period) {
      await new Promise<void>((resolve) => setTimeout(resolve, latencyMs))
      return mockUsage(period ?? new Date().toISOString().slice(0, 7))
    },
  }
}
