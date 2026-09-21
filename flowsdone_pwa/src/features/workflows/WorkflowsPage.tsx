import { Workflow } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

/** Placeholder: gestión de workflows y agentes (siguiente feature). */
export function WorkflowsPage() {
  return (
    <>
      <PageHeader title="Workflows" description="Agentes y automatizaciones de tu plataforma." />
      <EmptyState
        icon={Workflow}
        title="Próximamente"
        description="Aquí podrás ver, asignar y monitorear los workflows de Langflow y n8n."
      />
    </>
  )
}
