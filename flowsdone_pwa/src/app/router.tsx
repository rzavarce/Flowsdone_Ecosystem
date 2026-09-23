import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { PublicOnly } from '@/components/auth/PublicOnly'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { RequirePermission } from '@/components/auth/RequirePermission'
import { AppShell } from '@/components/layout/AppShell'
import type { Permission } from '@/core/auth/types'
import { AgentsPage } from '@/features/agents/AgentsPage'
import { ActivateAccountPage } from '@/features/auth/ActivateAccountPage'
import { ForgotPasswordPage } from '@/features/auth/ForgotPasswordPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { ResetPasswordPage } from '@/features/auth/ResetPasswordPage'
import { ChannelsPage } from '@/features/channels/ChannelsPage'
import { CompanyPage } from '@/features/company/CompanyPage'
import { ConversationsPage } from '@/features/conversations/ConversationsPage'
import { NotFoundPage } from '@/features/NotFoundPage'
import { OnboardingPage } from '@/features/onboarding/OnboardingPage'
import { PlansPage } from '@/features/plans/PlansPage'
import { ProfilePage } from '@/features/profile/ProfilePage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { SupportPage } from '@/features/support/SupportPage'
import { TenantsPage } from '@/features/tenants/TenantsPage'
import { UsersPage } from '@/features/users/UsersPage'
import { DashboardRoute } from './DashboardRoute'
import { RootRedirect } from './RootRedirect'

/** Wraps `element` behind a single required permission. */
const guarded = (permission: Permission, element: ReactNode) => (
  <RequirePermission anyOf={[permission]}>{element}</RequirePermission>
)

/**
 * Routes: `/` redirects (to login or the profile's home page); `/login` and
 * `/forgot-password` are public (they redirect away if there's already a
 * session); `/activate-account/:token` and `/reset-password/:token` are
 * public WITHOUT redirecting (see comment below); everything else requires
 * a session and, depending on the section, a permission.
 */
export const routes = [
  { path: '/', element: <RootRedirect /> },
  {
    path: '/login',
    element: (
      <PublicOnly>
        <LoginPage />
      </PublicOnly>
    ),
  },
  // Sin PublicOnly a propósito: son links de un solo uso que llegan por email y
  // deben funcionar pase lo que pase en la sesión de este navegador - si hubiera
  // una sesión de OTRA cuenta abierta acá (p. ej. un admin probando el link de
  // otro usuario), PublicOnly la redirigiría antes de mostrar el formulario y el
  // token nunca se canjearía. Al activar/restablecer, el propio flujo reemplaza
  // la sesión por la de la cuenta del token (ver ActivateAccountForm/ResetPasswordForm).
  { path: '/activate-account/:token', element: <ActivateAccountPage /> },
  { path: '/reset-password/:token', element: <ResetPasswordPage /> },
  {
    path: '/forgot-password',
    element: (
      <PublicOnly>
        <ForgotPasswordPage />
      </PublicOnly>
    ),
  },
  {
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { path: '/dashboard', element: <DashboardRoute /> },
      { path: '/profile', element: <ProfilePage /> },
      { path: '/support', element: <SupportPage /> },
      { path: '/conversations', element: guarded('conversations:manage', <ConversationsPage />) },
      { path: '/channels', element: guarded('channels:manage', <ChannelsPage />) },
      { path: '/tenants', element: guarded('projects:manage', <TenantsPage />) },
      { path: '/onboarding', element: guarded('tenants:manage', <OnboardingPage />) },
      { path: '/users', element: guarded('users:manage', <UsersPage />) },
      { path: '/agents', element: guarded('agents:edit', <AgentsPage />) },
      { path: '/company', element: guarded('company:view', <CompanyPage />) },
      { path: '/plans', element: guarded('platform:manage', <PlansPage />) },
      { path: '/settings', element: guarded('settings:view', <SettingsPage />) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

/** The browser router built from `routes`, used by `App`. */
export const router = createBrowserRouter(routes)
