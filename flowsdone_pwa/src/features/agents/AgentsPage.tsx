import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { LangflowEmbed } from './LangflowEmbed'
import { useTranslation } from 'react-i18next'

/**
 * Agents: the embedded Langflow editor, for any staff allowed to edit agents
 * (`admin`, `tenant_manager`, `botmaster` - the route already requires
 * `agents:edit` in `router.tsx`, so anyone who reaches this page already has
 * it). Opens as the user of the tenant chosen in the selector (only sees
 * that tenant's agents).
 *
 * The editor has a known security boundary, not specific to this screen:
 * whoever edits can add a component with Python code that runs inside the
 * Langflow container, and from there reaches shared environment variables
 * (`GATEWAY_ADMIN_API_KEY`, Langfuse/Weaviate credentials) and the internal
 * network - the per-user/folder separation in Langflow is cosmetic, not a
 * security boundary. Accepted knowingly for `tenant_manager`/`botmaster`
 * (Flowsdone staff, not clients) - see `POLICY["langflow"]` in the gateway.
 */
export function AgentsPage() {
  const { t } = useTranslation()
  const { current } = useTenant()

  return (
    <div className="flex h-full flex-col">
      <PageHeader title={t('nav.agents')} description={t('agents.description')} />
      {/* min-h-0: sin esto, un flex item no encoge por debajo del alto de su contenido y
          el editor de Langflow (que sí debe llenar el espacio disponible) se desborda. */}
      <div className="min-h-0 flex-1">
        <LangflowEmbed tenantId={current?.id} tenantName={current?.name} />
      </div>
    </div>
  )
}
