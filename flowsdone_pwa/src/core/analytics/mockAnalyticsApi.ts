import { REPORT_KEYS, type AnalyticsApi } from './analyticsApi'

/**
 * Mock adapter (demo mode and tests): an empty page instead of a Metabase
 * dashboard - there is no Metabase behind the mock console.
 */
export function createMockAnalyticsApi(): AnalyticsApi {
  return {
    async getDashboard(tenantId) {
      return { url: `about:blank#tenant=${tenantId ?? 'all'}`, dashboard: 'platform', expires_in: 3600 }
    },
    async listReports() {
      return [...REPORT_KEYS]
    },
    async getReport(report, tenantId) {
      return { url: `about:blank#${report}&tenant=${tenantId ?? 'all'}`, dashboard: report, expires_in: 3600 }
    },
  }
}
