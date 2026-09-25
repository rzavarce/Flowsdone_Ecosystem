import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { AnalyticsDashboard } from '@/features/dashboard/AnalyticsDashboard'
import { useTranslation } from 'react-i18next'

/**
 * Panel of the client side (`client` and `consultant`): the Metabase
 * dashboard of their own assistants - conversations, channels, busy hours
 * and plan usage - locked to their tenant.
 */
export function ClientPanel() {
  const { t } = useTranslation()
  const { current } = useTenant()
  return (
    <>
      <PageHeader
        title={t('reports.clientTitle')}
        description={current ? t('reports.resultsOf', { name: current.name }) : t('reports.resultsOwn')}
      />
      <AnalyticsDashboard title={t('reports.clientTitle')} />
    </>
  )
}
