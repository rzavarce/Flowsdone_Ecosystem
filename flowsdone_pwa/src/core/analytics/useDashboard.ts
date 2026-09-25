import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import type { AnalyticsApi, ReportKey } from './analyticsApi'
import { createAnalyticsApi } from './createAnalyticsApi'

/** Renew the signed URL this long before it expires. */
const RENEW_MARGIN_SECONDS = 120

/**
 * A dashboard for the active tenant (`undefined` = all the user's tenants):
 * the Dashboard section's one, or a report. The signed URL is renewed shortly
 * before it expires.
 *
 * @param tenantId - Tenant chosen in the top bar, if any.
 * @param report - Report to open; the profile's overview dashboard if omitted.
 * @param api - Injectable adapter (tests); created from the auth mode otherwise.
 */
export function useDashboard(tenantId?: string, report?: ReportKey, api?: AnalyticsApi) {
  const [client] = useState(() => api ?? createAnalyticsApi())
  return useQuery({
    queryKey: ['dashboard-embed', report ?? 'overview', tenantId ?? 'all'],
    queryFn: () => (report ? client.getReport(report, tenantId) : client.getDashboard(tenantId)),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const ttl = query.state.data?.expires_in
      return ttl ? Math.max(ttl - RENEW_MARGIN_SECONDS, 60) * 1000 : false
    },
    retry: 1,
  })
}

/**
 * Reports the user's profile can open (`GET /me/reports`), in display order.
 *
 * @param api - Injectable adapter (tests); created from the auth mode otherwise.
 */
export function useReports(api?: AnalyticsApi) {
  const [client] = useState(() => api ?? createAnalyticsApi())
  return useQuery({ queryKey: ['reports'], queryFn: () => client.listReports(), staleTime: Infinity })
}
