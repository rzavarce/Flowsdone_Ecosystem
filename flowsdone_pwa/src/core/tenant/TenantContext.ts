import { createContext } from 'react'
import type { Tenant } from '@/core/auth/types'

/** Valor que representa "todos los tenants" (solo administradores). */
export const ALL_TENANTS = 'all'

/** Valor expuesto por {@link TenantProvider}. */
export interface TenantContextValue {
  /** Tenants seleccionables por el usuario actual. */
  tenants: Tenant[]
  /** Si se ofrece la opción "Todos los tenants". */
  canSelectAll: boolean
  /** Tenant activo; `null` significa todos. */
  current: Tenant | null
  /** Id seleccionado (`ALL_TENANTS` o un id de tenant). */
  selectedId: string
  select: (id: string) => void
}

export const TenantContext = createContext<TenantContextValue | null>(null)
