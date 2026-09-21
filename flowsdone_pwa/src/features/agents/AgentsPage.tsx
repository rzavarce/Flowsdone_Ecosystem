import { PageHeader } from '@/components/layout/PageHeader'
import { LangflowEmbed } from './LangflowEmbed'

/** Editor de agentes: Langflow embebido para crear y ajustar flujos. */
export function AgentsPage() {
  return (
    <>
      <PageHeader title="Agentes" description="Diseña y ajusta los agentes de tu plataforma en Langflow." />
      <LangflowEmbed url={import.meta.env.VITE_LANGFLOW_URL} />
    </>
  )
}
