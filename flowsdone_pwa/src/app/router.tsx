import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { ChannelsPage } from '@/features/channels/ChannelsPage'
import { ConversationsPage } from '@/features/conversations/ConversationsPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { NotFoundPage } from '@/features/NotFoundPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { WorkflowsPage } from '@/features/workflows/WorkflowsPage'

/** Rutas de la aplicación; todas cuelgan del {@link AppShell}. */
export const routes = [
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/conversaciones', element: <ConversationsPage /> },
      { path: '/canales', element: <ChannelsPage /> },
      { path: '/workflows', element: <WorkflowsPage /> },
      { path: '/ajustes', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]

export const router = createBrowserRouter(routes)
