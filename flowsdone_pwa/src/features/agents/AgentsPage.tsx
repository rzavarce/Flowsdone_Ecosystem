import { PageHeader } from '@/components/layout/PageHeader'
import { useTenant } from '@/core/tenant/useTenant'
import { LangflowEmbed } from './LangflowEmbed'

/**
 * Agentes: el editor de Langflow embebido, para cualquier staff que pueda
 * editar agentes (`admin`, `tenant_manager`, `botmaster` - la ruta ya exige
 * `agents:edit` en `router.tsx`, así que quien llega acá siempre lo tiene).
 * Se abre como el usuario del tenant elegido en el selector (solo ve los
 * agentes de ese tenant).
 *
 * El editor tiene un límite de seguridad conocido, no de esta pantalla: quien
 * edita puede añadir un componente con código Python que corre en el
 * contenedor de Langflow, y desde ahí alcanza variables de entorno
 * compartidas (`GATEWAY_ADMIN_API_KEY`, credenciales de Langfuse/Weaviate) y
 * la red interna - la separación por usuario/carpeta en Langflow es de
 * vista, no de seguridad. Aceptado a sabiendas para `tenant_manager`/`botmaster`
 * (personal de Flowsdone, no de clientes) - ver `POLICY["langflow"]` en el gateway.
 */
export function AgentsPage() {
  const { current } = useTenant()

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Agentes" description="Diseña y ajusta los agentes de tu plataforma en Langflow." />
      {/* min-h-0: sin esto, un flex item no encoge por debajo del alto de su contenido y
          el editor de Langflow (que sí debe llenar el espacio disponible) se desborda. */}
      <div className="min-h-0 flex-1">
        <LangflowEmbed tenantId={current?.id} tenantName={current?.name} />
      </div>
    </div>
  )
}
