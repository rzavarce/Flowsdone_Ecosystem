import { render } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { routes } from '@/app/router'
import { AdminApiProvider } from '@/core/admin/AdminApiProvider'
import type { AdminApi } from '@/core/admin/AdminApi'
import { createMockAdminApi } from '@/core/admin/mockAdminApi'
import type { AuthApi } from '@/core/auth/AuthApi'
import { AuthProvider } from '@/core/auth/AuthProvider'
import type { Role, Tenant, User } from '@/core/auth/types'
import { TenantProvider } from '@/core/tenant/TenantProvider'
import { ThemeProvider } from '@/core/theme/ThemeProvider'

/** Tenants available to test users, used by `makeUser` to slice how many each role sees. */
export const TENANTS: Tenant[] = [
  { id: 't1', name: 'Clínica Vital' },
  { id: 't2', name: 'Inmobiliaria Norte' },
  { id: 't3', name: 'Tienda Aurora' },
]

/** Test user with the given role (admin sees all 3 tenants, manager 2, everyone else 1). */
export function makeUser(role: Role): User {
  const tenants = role === 'admin' ? TENANTS : role === 'tenant_manager' ? TENANTS.slice(0, 2) : TENANTS.slice(0, 1)
  return { id: `u-${role}`, name: `Persona ${role}`, email: `${role}@test.dev`, role, tenants }
}

/**
 * Fake adapter: `restore` returns the given user (or null = no session).
 * Profile edits apply to an in-memory copy, like the real server would, and
 * a photo is "served" from a fake URL keyed by `avatar_updated_at`.
 */
export function fakeAuthApi(user: User | null): AuthApi {
  let current = user ? { ...user } : null
  const requireUser = () => {
    if (!current) throw new Error('sin usuario')
    return current
  }
  const apply = (changes: Partial<User>) => (current = { ...requireUser(), ...changes })
  return {
    restore: async () => current,
    login: async () => requireUser(),
    logout: async () => {},
    activateAccount: async () => requireUser(),
    requestPasswordReset: async () => {},
    resetPassword: async () => requireUser(),
    updateProfile: async (patch) =>
      apply({
        ...(patch.name !== undefined ? { name: patch.name } : {}),
        ...(patch.phone !== undefined ? { phone: patch.phone || null } : {}),
        ...(patch.address !== undefined ? { address: patch.address || null } : {}),
        ...(patch.social_links !== undefined ? { social_links: patch.social_links } : {}),
      }),
    uploadAvatar: async () => apply({ avatar_updated_at: '2026-09-23T10:00:00Z' }),
    removeAvatar: async () => apply({ avatar_updated_at: null }),
    avatarUrl: (u) => (u.avatar_updated_at ? `/fake-avatar/${u.id}?v=${u.avatar_updated_at}` : null),
  }
}

/**
 * Renders the full app (providers + real routes) at `path`.
 *
 * @param path - Initial route.
 * @param api - Auth adapter (use `fakeAuthApi`).
 * @param adminApi - Admin API adapter; defaults to the latency-free mock.
 */
export function renderApp(path: string, api: AuthApi, adminApi: AdminApi = createMockAdminApi({ latencyMs: 0 })) {
  return render(
    <ThemeProvider>
      <AuthProvider api={api}>
        <TenantProvider>
          <AdminApiProvider api={adminApi}>
            <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
          </AdminApiProvider>
        </TenantProvider>
      </AuthProvider>
    </ThemeProvider>,
  )
}
