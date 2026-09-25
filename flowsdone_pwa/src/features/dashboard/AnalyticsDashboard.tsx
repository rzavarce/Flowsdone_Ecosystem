import { BarChart3 } from 'lucide-react'
import { iframeResizer } from 'iframe-resizer'
import { useEffect, useRef, type RefObject } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Spinner } from '@/components/ui/Spinner'
import type { AnalyticsApi, ReportKey } from '@/core/analytics/analyticsApi'
import { useDashboard } from '@/core/analytics/useDashboard'
import { ApiError } from '@/core/http/apiFetch'
import { useTenant } from '@/core/tenant/useTenant'

/** Height before Metabase reports its own (and the minimum after). */
const MIN_HEIGHT = 600

/**
 * Grows the iframe to the dashboard's height, so the page has a single
 * scrollbar. Metabase embeds speak the iframe-resizer protocol; only
 * messages from Metabase's own origin are accepted.
 */
function useAutoHeight(frame: RefObject<HTMLIFrameElement | null>, src: string | undefined) {
  useEffect(() => {
    const element = frame.current
    if (!element || !src) return
    let origin: string
    try {
      origin = new URL(src).origin
    } catch {
      return
    }
    const [resized] = iframeResizer({ checkOrigin: [origin], log: false, minHeight: MIN_HEIGHT, warningTimeout: 0 }, element)
    return () => resized?.iFrameResizer?.removeListeners()
  }, [frame, src])
}

/**
 * A Metabase dashboard - the Dashboard section's one, or a report - for the
 * tenant chosen in the top bar (or all the user's tenants). Which dashboard
 * and which tenants is decided by the gateway and locked inside the signed URL.
 */
export function AnalyticsDashboard({ title, report, api }: { title: string; report?: ReportKey; api?: AnalyticsApi }) {
  const { t } = useTranslation()
  const { current } = useTenant()
  const dashboard = useDashboard(current?.id, report, api)
  const frame = useRef<HTMLIFrameElement>(null)
  useAutoHeight(frame, dashboard.data?.url)

  if (dashboard.isPending) return <Spinner label={t('dashboard.analytics.loading')} className="py-24" />
  if (dashboard.isError) {
    const status = dashboard.error instanceof ApiError ? dashboard.error.status : 0
    if (status === 403) {
      return <EmptyState icon={BarChart3} title={t('dashboard.analytics.noTenantTitle')} description={t('dashboard.analytics.noTenant')} />
    }
    return (
      <Alert tone="danger">
        <p>{status === 503 ? t('dashboard.analytics.unavailable') : t('dashboard.analytics.error')}</p>
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => void dashboard.refetch()}>
          {t('common.retry')}
        </Button>
      </Alert>
    )
  }
  return (
    <Card className="overflow-hidden p-0">
      <iframe
        ref={frame}
        key={dashboard.data.url}
        src={dashboard.data.url}
        title={title}
        className="block w-full border-0 bg-transparent"
        style={{ minHeight: MIN_HEIGHT }}
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    </Card>
  )
}
