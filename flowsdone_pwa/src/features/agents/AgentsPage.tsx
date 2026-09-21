import { PageHeader } from '@/components/layout/PageHeader'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { LangflowEmbed } from './LangflowEmbed'
import { TenantAgents } from './TenantAgents'

/**
 * Agentes.
 *
 * - **Admin** (equipo de la plataforma): el editor de Langflow embebido.
 * - **Resto** (gestores, botmasters): solo la lista de agentes de su tenant.
 *
 * El editor de Langflow NO se ofrece a nadie más a propósito: Langflow no tiene
 * multi-tenancy (una sola cuenta es dueña de todos los flujos), así que quien
 * abra su interfaz ve los flujos de todos los clientes, sus variables guardadas
 * y puede ejecutar código en su contenedor. Se usa `platform:manage` (solo admin)
 * porque es una capacidad de la plataforma, no de un tenant.
 */
export function AgentsPage() {
  const { user } = useAuth()
  const platformStaff = can(user, 'platform:manage')

  return (
    <>
      <PageHeader
        title="Agentes"
        description={platformStaff ? 'Diseña y ajusta los agentes de tu plataforma en Langflow.' : 'Los agentes de tus tenants.'}
      />
      {platformStaff ? <LangflowEmbed url={import.meta.env.VITE_LANGFLOW_URL} /> : <TenantAgents />}
    </>
  )
}
