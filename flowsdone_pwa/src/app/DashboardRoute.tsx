import { Navigate } from 'react-router-dom'
import { can, homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ClientPanel } from '@/features/reports/ClientPanel'

/**
 * Contenido de /dashboard según el perfil: dashboard operativo, panel de solo
 * lectura del cliente, o redirección a la sección propia (botmaster).
 */
export function DashboardRoute() {
  const { user } = useAuth()
  if (!user) return null
  if (can(user, 'dashboard:view')) return <DashboardPage />
  if (can(user, 'reports:view')) return <ClientPanel />
  return <Navigate to={homePathFor(user)} replace />
}
