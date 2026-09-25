import { Navigate } from 'react-router-dom'
import { can, homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ClientPanel } from '@/features/reports/ClientPanel'

/**
 * Content for /dashboard based on the profile: the staff's platform
 * dashboard, the client side's panel (`client` and `consultant`), or a
 * redirect to the user's own section. Both screens embed a Metabase
 * dashboard; the gateway picks which one and locks its tenants.
 */
export function DashboardRoute() {
  const { user } = useAuth()
  if (!user) return null
  if (can(user, 'dashboard:view')) return <DashboardPage />
  if (can(user, 'reports:view')) return <ClientPanel />
  return <Navigate to={homePathFor(user)} replace />
}
