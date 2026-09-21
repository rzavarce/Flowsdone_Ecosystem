import { MessageSquare } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'

/** Placeholder: bandeja de conversaciones (siguiente feature). */
export function ConversationsPage() {
  return (
    <>
      <PageHeader title="Conversaciones" description="Bandeja unificada de todos los canales." />
      <EmptyState
        icon={MessageSquare}
        title="Próximamente"
        description="Aquí vivirá la bandeja de conversaciones en tiempo real, con intervención humana sobre el agente."
      />
    </>
  )
}
