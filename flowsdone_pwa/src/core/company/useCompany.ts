import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { createCompanyApi } from './createCompanyApi'

/**
 * Billing data for the logged-in user's tenant (intended for `client`
 * accounts). `data` is `null` (not an error) if nothing has been saved yet -
 * see `GET /me/billing-profile`.
 */
export function useCompany() {
  const [api] = useState(() => createCompanyApi())
  return useQuery({ queryKey: ['my-company'], queryFn: () => api.getMyCompany() })
}

/**
 * Usage and charges of the logged-in user's tenant for a month (current if
 * `period` is omitted) - `GET /me/usage`, `client` accounts only.
 */
export function useMyUsage(period?: string) {
  const [api] = useState(() => createCompanyApi())
  return useQuery({ queryKey: ['my-usage', period ?? 'current'], queryFn: () => api.getMyUsage(period) })
}
