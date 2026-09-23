import { useContext } from 'react'
import { TenantContext, type TenantContextValue } from './TenantContext'

/**
 * Accesses the active tenant.
 *
 * @throws Error if used outside `<TenantProvider>`.
 */
export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant debe usarse dentro de <TenantProvider>')
  return ctx
}
