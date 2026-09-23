import { Navigate } from 'react-router-dom'
import { can, homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { ClientPanel } from '@/features/reports/ClientPanel'
import { ReportsPlaceholder } from '@/features/reports/ReportsPlaceholder'

/**
 * Content for /dashboard based on the profile: operational dashboard, the
 * client's read-only panel, the consultant's reports placeholder, or a
 * redirect to the user's own section (botmaster).
 *
 * `consultant` is resolved by ROLE, not by permission, ahead of the generic
 * `reports:view` check: it shares that permission with `client` (both "view
 * reports"), but each lands on a different screen - `client` stays on
 * `ClientPanel` (its usual panel); `consultant` is exclusive to
 * `ReportsPlaceholder`, the placeholder reserved for the Metabase dashboards.
 */
export function DashboardRoute() {
  const { user } = useAuth()
  if (!user) return null
  if (can(user, 'dashboard:view')) return <DashboardPage />
  if (user.role === 'consultant') return <ReportsPlaceholder />
  if (can(user, 'reports:view')) return <ClientPanel />
  return <Navigate to={homePathFor(user)} replace />
}
