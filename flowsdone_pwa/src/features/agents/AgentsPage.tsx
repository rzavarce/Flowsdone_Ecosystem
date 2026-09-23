import { Building2 } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { useTenant } from '@/core/tenant/useTenant'
import { cn } from '@/lib/cn'
import { AgentsPanel } from './AgentsPanel'
import { LangflowEmbed } from './LangflowEmbed'
import { useTranslation } from 'react-i18next'

type Tab = 'list' | 'editor'

/**
 * Agents, for any staff allowed to edit them (`admin`, `tenant_manager`,
 * `botmaster` - the route already requires `agents:edit` in `router.tsx`).
 * Two tabs over the tenant chosen in the selector:
 *
 * - **Agents**: the tenant's agents per project - registering a flow of the
 *   project's Langflow folder as an agent, editing, making default,
 *   suspending and deleting them (`AgentsPanel`).
 * - **Langflow editor**: the embedded editor, opened as the tenant's own
 *   Langflow user (only sees that tenant's folders). Flows are imported or
 *   built here, then registered in the first tab.
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
  const [tab, setTab] = useState<Tab>('list')

  return (
    <div className="flex h-full flex-col">
      <PageHeader title={t('nav.agents')} description={t('agents.description')} />
      {!current ? (
        <EmptyState icon={Building2} title={t('agents.pickTenant.title')} description={t('agents.pickTenant.description')} />
      ) : (
        <>
          <div role="tablist" aria-label={t('nav.agents')} className="mb-6 inline-flex self-start rounded-xl bg-surface-muted p-1">
            {(['list', 'editor'] as const).map((id) => (
              <button
                key={id}
                role="tab"
                type="button"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={cn(
                  'cursor-pointer rounded-lg px-4 py-1.5 text-sm font-medium transition',
                  tab === id ? 'bg-surface text-foreground shadow-theme-xs' : 'text-muted hover:text-foreground',
                )}
              >
                {t(`agents.tabs.${id}`)}
              </button>
            ))}
          </div>
          {tab === 'list' ? (
            <AgentsPanel key={current.id} tenantId={current.id} />
          ) : (
            // min-h-0: sin esto, un flex item no encoge por debajo del alto de su contenido y
            // el editor de Langflow (que sí debe llenar el espacio disponible) se desborda.
            <div className="min-h-0 flex-1">
              <LangflowEmbed tenantId={current.id} tenantName={current.name} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
