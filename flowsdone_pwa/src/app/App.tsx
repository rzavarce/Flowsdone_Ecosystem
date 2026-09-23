import { useTranslation } from 'react-i18next'
import { RouterProvider } from 'react-router-dom'
import { AdminApiProvider } from '@/core/admin/AdminApiProvider'
import { AuthProvider } from '@/core/auth/AuthProvider'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { TenantProvider } from '@/core/tenant/TenantProvider'
import { router } from './router'

/**
 * Application root: global providers + router.
 *
 * The router is keyed by the language: switching it remounts the screens so
 * every text (including module-level catalogs read through getters, like the
 * menu or the channel types) is rendered again in the new language. Session,
 * tenant and query cache live above it and survive the switch.
 */
export function App() {
  const { i18n } = useTranslation()
  return (
    <ThemeProvider>
      <AuthProvider>
        <TenantProvider>
          <AdminApiProvider>
            <RouterProvider key={i18n.language} router={router} />
          </AdminApiProvider>
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
