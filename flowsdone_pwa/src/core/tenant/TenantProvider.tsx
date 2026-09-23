import { useMemo, useState, type ReactNode } from 'react'
import { useAuth } from '@/core/auth/useAuth'
import { ALL_TENANTS, TenantContext, type TenantContextValue } from './TenantContext'

/**
 * Tenant the user is currently working on. Admins can view "all"; everyone
 * else is scoped to their assigned tenants. If the selection stops being
 * valid (e.g. a different user logs in), the default value is recomputed
 * with no side effects.
 */
export function TenantProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [requestedId, setRequestedId] = useState<string>(ALL_TENANTS)

  const value = useMemo<TenantContextValue>(() => {
    const tenants = user?.tenants ?? []
    const canSelectAll = user?.role === 'admin'
    const valid = (id: string) =>
      (id === ALL_TENANTS && canSelectAll) || tenants.some((t) => t.id === id)
    const selectedId = valid(requestedId) ? requestedId : canSelectAll ? ALL_TENANTS : (tenants[0]?.id ?? ALL_TENANTS)
    return {
      tenants,
      canSelectAll,
      selectedId,
      current: tenants.find((t) => t.id === selectedId) ?? null,
      select: setRequestedId,
    }
  }, [user, requestedId])

  return <TenantContext value={value}>{children}</TenantContext>
}
