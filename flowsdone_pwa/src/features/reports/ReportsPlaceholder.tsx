import { LineChart } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { useTranslation } from 'react-i18next'

/** Placeholder for the `consultant` role: embedded Metabase dashboards (upcoming feature). */
export function ReportsPlaceholder() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('reports.title')} description={t('reports.description')} />
      <EmptyState
        icon={LineChart}
        title={t('common.comingSoon')}
        description={t('reports.comingSoon')}
      />
    </>
  )
}
