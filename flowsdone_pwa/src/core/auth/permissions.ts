import type { Permission, Role, User } from './types'

/** Display name and short description of each profile. */
export const ROLE_META: Record<Role, { label: string; description: string }> = {
  admin: { label: 'Administrador', description: 'Gestiona toda la plataforma y todos los tenants.' },
  tenant_manager: { label: 'Gestor de tenant', description: 'Gestiona por completo los tenants asignados.' },
  botmaster: { label: 'Botmaster', description: 'Crea y ajusta agentes en Langflow.' },
  client: { label: 'Cliente', description: 'Consulta gráficos y paneles de su organización.' },
  consultant: { label: 'Consultor', description: 'Consultor externo de un cliente: solo ve reportes.' },
}

/** Role -> permissions matrix. The single source of truth for access control in the UI. */
export const ROLE_PERMISSIONS: Record<Role, readonly Permission[]> = {
  admin: [
    'dashboard:view',
    'reports:view',
    'conversations:manage',
    'channels:manage',
    'agents:edit',
    'settings:view',
    'projects:manage',
    'tenants:manage',
    'platform:manage',
    'users:manage',
  ],
  tenant_manager: [
    'dashboard:view',
    'reports:view',
    'conversations:manage',
    'channels:manage',
    'agents:edit',
    'settings:view',
    'projects:manage',
  ],
  // Staff de Flowsdone asignado a tenants concretos por un admin: agentes,
  // canales y conversaciones de esos tenants (POLICY.channel_connections en
  // el backend, ampliado junto con esto - ver access_control.py).
  botmaster: ['agents:edit', 'settings:view', 'channels:manage', 'conversations:manage'],
  client: ['reports:view', 'settings:view', 'company:view'],
  // Consultor de un cliente: solo reportes (ni dashboard, ni los datos de
  // facturación de la empresa - eso es exclusivo de client).
  consultant: ['reports:view', 'settings:view'],
}

/**
 * Whether the user has at least one of the requested permissions.
 *
 * Only controls **visibility in the UI**: real authorization must be
 * enforced by the backend on each endpoint.
 *
 * @param user - Current user, or `null` if there is no session.
 * @param permissions - Acceptable permissions (one is enough).
 * @returns `true` if they have any; always `false` without a user.
 */
export function can(user: User | null, ...permissions: Permission[]): boolean {
  if (!user) return false
  const granted = ROLE_PERMISSIONS[user.role]
  return permissions.some((p) => granted.includes(p))
}

/**
 * Route the user is sent to after logging in.
 *
 * @param user - Authenticated user.
 * @returns `/dashboard` for those who can view dashboards, `/agents` for the
 *   botmaster and `/settings` as a last resort.
 */
export function homePathFor(user: User): string {
  if (can(user, 'dashboard:view', 'reports:view')) return '/dashboard'
  if (can(user, 'agents:edit')) return '/agents'
  return '/settings'
}
