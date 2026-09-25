import { apiFetch } from '@/core/http/apiFetch'

/** Reports of the Reports section, in display order (see `GET /me/reports`). */
export const REPORT_KEYS = ['report_channels', 'report_agents', 'report_contacts', 'report_hours', 'report_usage'] as const
export type ReportKey = (typeof REPORT_KEYS)[number]

/** Which dashboard the gateway chose (the profile's overview, or a report). */
export type DashboardKind = 'platform' | 'platform_admin' | 'client' | ReportKey

/** A dashboard ready to show (`GET /me/dashboard`). */
export interface DashboardEmbed {
  /** Signed, short-lived Metabase URL to load in an iframe. */
  url: string
  dashboard: DashboardKind
  /** Seconds the URL stays valid. */
  expires_in: number
}

/**
 * Dashboards of the console (Metabase, static embedding). The gateway picks
 * the dashboard for the user's profile and locks its tenant filter inside the
 * signed URL: the browser can't widen it.
 */
export interface AnalyticsApi {
  /**
   * The Dashboard section's dashboard, restricted to `tenantId` (one of the
   * user's tenants) or, without it, to all the user's tenants.
   */
  getDashboard(tenantId?: string): Promise<DashboardEmbed>
  /** Reports the user's profile can open, in display order (`GET /me/reports`). */
  listReports(): Promise<ReportKey[]>
  /** One report, with the same tenant rules as {@link getDashboard} (`GET /me/reports/{key}`). */
  getReport(report: ReportKey, tenantId?: string): Promise<DashboardEmbed>
}

/** HTTP adapter over `GET /me/dashboard` and `GET /me/reports[/{key}]`. */
export function createHttpAnalyticsApi(baseUrl = '/api', fetchFn?: typeof fetch): AnalyticsApi {
  return {
    getDashboard(tenantId) {
      const qs = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''
      return apiFetch<DashboardEmbed>(`/me/dashboard${qs}`, { baseUrl, fetchFn })
    },
    async listReports() {
      const { reports } = await apiFetch<{ reports: ReportKey[] }>('/me/reports', { baseUrl, fetchFn })
      return reports
    },
    getReport(report, tenantId) {
      const qs = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : ''
      return apiFetch<DashboardEmbed>(`/me/reports/${encodeURIComponent(report)}${qs}`, { baseUrl, fetchFn })
    },
  }
}
