import { RouterProvider } from 'react-router-dom'
import { AdminApiProvider } from '@/core/admin/AdminApiProvider'
import { AuthProvider } from '@/core/auth/AuthProvider'
import { ThemeProvider } from '@/core/theme/ThemeProvider'
import { TenantProvider } from '@/core/tenant/TenantProvider'
import { router } from './router'

/** Raíz de la aplicación: proveedores globales + router. */
export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <TenantProvider>
          <AdminApiProvider>
            <RouterProvider router={router} />
          </AdminApiProvider>
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
