import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

const resizer = vi.hoisted(() => ({ iframeResizer: vi.fn(() => [{ iFrameResizer: { removeListeners: vi.fn() } }]) }))
vi.mock('iframe-resizer', () => resizer)
import type { AnalyticsApi } from '@/core/analytics/analyticsApi'
import { ApiError } from '@/core/http/apiFetch'
import { TenantContext, type TenantContextValue } from '@/core/tenant/TenantContext'
import { AnalyticsDashboard } from './AnalyticsDashboard'

const URL_ = 'https://bi.flowsdone.com/embed/dashboard/tok#bordered=false'

/** An AnalyticsApi with only what a test needs. */
const fakeApi = (overrides: Partial<AnalyticsApi>): AnalyticsApi => ({
  getDashboard: async () => ({ url: URL_, dashboard: 'platform', expires_in: 3600 }),
  listReports: async () => [],
  getReport: async (report) => ({ url: URL_, dashboard: report, expires_in: 3600 }),
  ...overrides,
})

function renderWith(api: AnalyticsApi, current: { id: string; name: string } | null = { id: 't1', name: 'Clínica' }) {
  const tenant: TenantContextValue = { tenants: [], canSelectAll: true, current, selectedId: current?.id ?? 'all', select: () => {} }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrap = (node: ReactNode) => (
    <QueryClientProvider client={client}>
      <TenantContext.Provider value={tenant}>{node}</TenantContext.Provider>
    </QueryClientProvider>
  )
  return render(wrap(<AnalyticsDashboard title="Dashboard" api={api} />))
}

describe('AnalyticsDashboard', () => {
  it('pide el dashboard del tenant activo y lo muestra en un iframe', async () => {
    const getDashboard = vi.fn(async () => ({ url: URL_, dashboard: 'platform' as const, expires_in: 3600 }))
    renderWith(fakeApi({ getDashboard }))
    const frame = await screen.findByTitle('Dashboard')
    expect(frame).toHaveAttribute('src', URL_)
    expect(getDashboard).toHaveBeenCalledWith('t1')
  })

  it('con "todos los tenants" no manda tenant', async () => {
    const getDashboard = vi.fn(async () => ({ url: URL_, dashboard: 'platform_admin' as const, expires_in: 3600 }))
    renderWith(fakeApi({ getDashboard }), null)
    await screen.findByTitle('Dashboard')
    expect(getDashboard).toHaveBeenCalledWith(undefined)
  })

  it('ajusta la altura con iframe-resizer aceptando solo mensajes del origen de Metabase', async () => {
    renderWith(fakeApi({ getDashboard: async () => ({ url: URL_, dashboard: 'client', expires_in: 3600 }) }))
    const frame = await screen.findByTitle('Dashboard')
    expect(resizer.iframeResizer).toHaveBeenCalledWith(
      expect.objectContaining({ checkOrigin: ['https://bi.flowsdone.com'], minHeight: 600 }),
      frame,
    )
  })

  it('explica cuando los dashboards no están disponibles o la cuenta no tiene tenants', async () => {
    const { unmount } = renderWith(fakeApi({ getDashboard: async () => { throw new ApiError(503, 'dashboards unavailable') } }))
    expect(await screen.findByText(/no están disponibles ahora mismo/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
    unmount()

    renderWith(fakeApi({ getDashboard: async () => { throw new ApiError(403, 'no tenant') } }))
    expect(await screen.findByText('Sin tenants asignados')).toBeInTheDocument()
  })
})
