import type { ReactNode } from 'react'
import { createBrowserRouter } from 'react-router-dom'
import { PublicOnly } from '@/components/auth/PublicOnly'
import { RequireAuth } from '@/components/auth/RequireAuth'
import { RequirePermission } from '@/components/auth/RequirePermission'
import { AppShell } from '@/components/layout/AppShell'
import type { Permission } from '@/core/auth/types'
import { AgentsPage } from '@/features/agents/AgentsPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { ChannelsPage } from '@/features/channels/ChannelsPage'
import { ConversationsPage } from '@/features/conversations/ConversationsPage'
import { NotFoundPage } from '@/features/NotFoundPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { TenantsPage } from '@/features/tenants/TenantsPage'
import { DashboardRoute } from './DashboardRoute'
import { RootRedirect } from './RootRedirect'

const guarded = (permission: Permission, element: ReactNode) => (
  <RequirePermission anyOf={[permission]}>{element}</RequirePermission>
)

/**
 * Rutas: `/` redirige (login o inicio del perfil), `/login` es pública; el
 * resto exige sesión y, según la sección, un permiso.
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
      { path: '/agentes', element: guarded('agents:edit', <AgentsPage />) },
      { path: '/ajustes', element: guarded('settings:view', <SettingsPage />) },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
