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
import { SettingsPage } from '@/features/settings/SettingsPage'
import { TenantsPage } from '@/features/tenants/TenantsPage'
import { UsersPage } from '@/features/users/UsersPage'
import { DashboardRoute } from './DashboardRoute'
import { RootRedirect } from './RootRedirect'

const guarded = (permission: Permission, element: ReactNode) => (
  <RequirePermission anyOf={[permission]}>{element}</RequirePermission>
)

/**
 * Rutas: `/` redirige (login o inicio del perfil); `/login` y `/recuperar-password`
 * son públicas (redirigen si ya hay sesión); `/activar-cuenta/:token` y
 * `/restablecer-password/:token` son públicas SIN redirigir (ver comentario abajo);
 * el resto exige sesión y, según la sección, un permiso.
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
  { path: '/activar-cuenta/:token', element: <ActivateAccountPage /> },
  { path: '/restablecer-password/:token', element: <ResetPasswordPage /> },
  {
    path: '/recuperar-password',
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
      { path: '/conversaciones', element: guarded('conversations:manage', <ConversationsPage />) },
      { path: '/canales', element: guarded('channels:manage', <ChannelsPage />) },
      { path: '/tenants', element: guarded('projects:manage', <TenantsPage />) },
      { path: '/usuarios', element: guarded('users:manage', <UsersPage />) },
      { path: '/agentes', element: guarded('agents:edit', <AgentsPage />) },
      { path: '/mi-empresa', element: guarded('company:view', <CompanyPage />) },
      { path: '/ajustes', element: guarded('settings:view', <SettingsPage />) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
