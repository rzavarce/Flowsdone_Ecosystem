import { PageHeader } from '@/components/layout/PageHeader'
import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { useTenant } from '@/core/tenant/useTenant'
import { LangflowEmbed } from './LangflowEmbed'
import { TenantAgents } from './TenantAgents'

/**
 * Agentes.
 *
 * - **Admin** (equipo de la plataforma): el editor de Langflow embebido, abierto como
 *   el usuario del tenant elegido en el selector (solo ve los agentes de ese tenant).
 * - **Resto** (gestores, botmasters): solo la lista de agentes de su tenant.
 *
 * El editor NO se ofrece a nadie más a propósito: separar por usuario y carpeta en
 * Langflow es una separación de vista, no de seguridad. Quien edita puede añadir un
 * componente con código Python que corre en el contenedor de Langflow, y desde ahí
 * alcanza sus variables de entorno y la red interna. Se usa `platform:manage` (solo
 * admin) porque es una capacidad de la plataforma, no de un tenant.
 */
export function AgentsPage() {
  const { user } = useAuth()
  const platformStaff = can(user, 'platform:manage')
  const { current } = useTenant()

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Agentes"
        description={platformStaff ? 'Diseña y ajusta los agentes de tu plataforma en Langflow.' : 'Los agentes de tus tenants.'}
      />
      {/* min-h-0: sin esto, un flex item no encoge por debajo del alto de su contenido y
          el editor de Langflow (que sí debe llenar el espacio disponible) se desborda. */}
      <div className="min-h-0 flex-1">
        {platformStaff ? <LangflowEmbed tenantId={current?.id} tenantName={current?.name} /> : <TenantAgents />}
      </div>
    </div>
  )
}
