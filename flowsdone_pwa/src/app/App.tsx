import { RouterProvider } from 'react-router-dom'
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
          <RouterProvider router={router} />
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>
  )
}
