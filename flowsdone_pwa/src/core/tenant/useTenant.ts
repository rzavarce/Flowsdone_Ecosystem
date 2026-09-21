import { useContext } from 'react'
import { TenantContext, type TenantContextValue } from './TenantContext'

/**
 * Accede al tenant activo.
 *
 * @throws Error si se usa fuera de `<TenantProvider>`.
 */
export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant debe usarse dentro de <TenantProvider>')
  return ctx
}
