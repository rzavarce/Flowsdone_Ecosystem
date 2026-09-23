import { LineChart } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

/** Placeholder para el perfil `consultant`: dashboards de Metabase embebidos (siguiente feature). */
export function ReportsPlaceholder() {
  return (
    <>
      <PageHeader title="Reportes" description="Indicadores y dashboards de tus clientes." />
      <EmptyState
        icon={LineChart}
        title="Próximamente"
        description="Aquí se embeberán los dashboards de Metabase con los reportes de tus clientes."
      />
    </>
  )
}
