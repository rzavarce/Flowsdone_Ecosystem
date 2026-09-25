import { AUTH_MODE } from '@/core/auth/createAuthApi'
import { createHttpAnalyticsApi, type AnalyticsApi } from './analyticsApi'
import { createMockAnalyticsApi } from './mockAnalyticsApi'

/** Instantiates the dashboards adapter according to {@link AUTH_MODE} (same mode as auth/admin). */
export function createAnalyticsApi(): AnalyticsApi {
  return AUTH_MODE === 'mock' ? createMockAnalyticsApi() : createHttpAnalyticsApi(import.meta.env.VITE_API_BASE_URL)
}
