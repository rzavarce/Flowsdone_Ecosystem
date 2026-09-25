import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { useTranslation } from 'react-i18next'
import { AnalyticsDashboard } from './AnalyticsDashboard'

/**
 * Staff overview: the platform's Metabase dashboard (performance and usage;
 * admins also get the business block), for the tenant chosen in the top bar
 * or for all of them.
 */
export function DashboardPage() {
  const { t } = useTranslation()
  const { current } = useTenant()
  return (
    <>
      <PageHeader
        title={t('nav.dashboard')}
        description={current ? t('dashboard.descriptionTenant', { name: current.name }) : t('dashboard.descriptionAll')}
      />
      <AnalyticsDashboard title={t('nav.dashboard')} />
    </>
  )
}
