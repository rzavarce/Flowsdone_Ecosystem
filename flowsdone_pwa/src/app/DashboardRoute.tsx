import { Navigate } from 'react-router-dom'
import { can, homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ClientPanel } from '@/features/reports/ClientPanel'
import { ReportsPlaceholder } from '@/features/reports/ReportsPlaceholder'

/**
 * Contenido de /dashboard según el perfil: dashboard operativo, panel de solo
 * lectura del cliente, el placeholder de reportes del consultor, o
 * redirección a la sección propia (botmaster).
 *
 * `consultant` se resuelve por ROL, no por permiso, antes del chequeo
 * genérico de `reports:view`: comparte ese permiso con `client` (ambos "ven
 * reportes"), pero cada uno cae en una pantalla distinta - `client` sigue en
 * `ClientPanel` (su panel de siempre); `consultant` es exclusivo de
 * `ReportsPlaceholder`, el hueco pensado para los dashboards de Metabase.
 */
export function DashboardRoute() {
  const { user } = useAuth()
  if (!user) return null
  if (can(user, 'dashboard:view')) return <DashboardPage />
  if (user.role === 'consultant') return <ReportsPlaceholder />
  if (can(user, 'reports:view')) return <ClientPanel />
  return <Navigate to={homePathFor(user)} replace />
}
