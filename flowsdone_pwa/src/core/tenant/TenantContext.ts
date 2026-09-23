import { createContext } from 'react'
import type { Tenant } from '@/core/auth/types'

/** Value representing "all tenants" (admins only). */
export const ALL_TENANTS = 'all'

/** Value exposed by {@link TenantProvider}. */
export interface TenantContextValue {
  /** Tenants the current user can select. */
  tenants: Tenant[]
  /** Whether the "All tenants" option is offered. */
  canSelectAll: boolean
  /** Active tenant; `null` means all of them. */
  current: Tenant | null
  /** Selected id (`ALL_TENANTS` or a tenant id). */
  selectedId: string
  select: (id: string) => void
}

/** React context carrying the current {@link TenantContextValue}; `null` outside `<TenantProvider>`. */
export const TenantContext = createContext<TenantContextValue | null>(null)
