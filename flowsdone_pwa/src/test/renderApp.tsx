import { render } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { routes } from '@/app/router'
import type { AuthApi } from '@/core/auth/AuthApi'
import { AuthProvider } from '@/core/auth/AuthProvider'
import type { Role, Tenant, User } from '@/core/auth/types'
import { TenantProvider } from '@/core/tenant/TenantProvider'
import { ThemeProvider } from '@/core/theme/ThemeProvider'

export const TENANTS: Tenant[] = [
  { id: 't1', name: 'Clínica Vital' },
  { id: 't2', name: 'Inmobiliaria Norte' },
  { id: 't3', name: 'Tienda Aurora' },
]

/** Usuario de prueba con el rol dado (admin ve los 3 tenants, gestor 2, el resto 1). */
export function makeUser(role: Role): User {
  const tenants = role === 'admin' ? TENANTS : role === 'tenant_manager' ? TENANTS.slice(0, 2) : TENANTS.slice(0, 1)
  return { id: `u-${role}`, name: `Persona ${role}`, email: `${role}@test.dev`, role, tenants }
}

/** Adaptador falso: `restore` devuelve el usuario dado (o null = sin sesión). */
export function fakeAuthApi(user: User | null): AuthApi {
  return {
    restore: async () => user,
    login: async () => {
      if (!user) throw new Error('sin usuario')
      return user
    },
    logout: async () => {},
  }
}

/** Renderiza la app completa (providers + rutas reales) en `path`. */
export function renderApp(path: string, api: AuthApi) {
  return render(
    <ThemeProvider>
      <AuthProvider api={api}>
        <TenantProvider>
          <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>,
  )
}
