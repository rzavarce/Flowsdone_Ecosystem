import type { Permission, Role, User } from './types'

/** Nombre visible y descripción corta de cada perfil. */
export const ROLE_META: Record<Role, { label: string; description: string }> = {
  admin: { label: 'Administrador', description: 'Gestiona toda la plataforma y todos los tenants.' },
  tenant_manager: { label: 'Gestor de tenant', description: 'Gestiona por completo los tenants asignados.' },
  botmaster: { label: 'Botmaster', description: 'Crea y ajusta agentes en Langflow.' },
  client: { label: 'Cliente', description: 'Consulta gráficos y paneles de su organización.' },
}

/** Matriz rol -> permisos. Única fuente de verdad del control de acceso en la UI. */
export const ROLE_PERMISSIONS: Record<Role, readonly Permission[]> = {
  admin: ['dashboard:view', 'reports:view', 'conversations:manage', 'channels:manage', 'agents:edit', 'settings:view', 'platform:manage'],
  tenant_manager: ['dashboard:view', 'reports:view', 'conversations:manage', 'channels:manage', 'agents:edit', 'settings:view'],
  botmaster: ['agents:edit', 'settings:view'],
  client: ['reports:view', 'settings:view'],
}

/**
 * Indica si el usuario tiene al menos uno de los permisos pedidos.
 *
 * Solo controla la **visibilidad en la UI**: la autorización real debe
 * imponerla el backend en cada endpoint.
 *
 * @param user - Usuario actual o `null` si no hay sesión.
 * @param permissions - Permisos aceptables (basta uno).
 * @returns `true` si tiene alguno; siempre `false` sin usuario.
 */
export function can(user: User | null, ...permissions: Permission[]): boolean {
  if (!user) return false
  const granted = ROLE_PERMISSIONS[user.role]
  return permissions.some((p) => granted.includes(p))
}

/**
 * Ruta a la que se envía al usuario tras iniciar sesión.
 *
 * @param user - Usuario autenticado.
 * @returns `/dashboard` para quien ve dashboards, `/agentes` para el
 *   botmaster y `/ajustes` como último recurso.
 */
export function homePathFor(user: User): string {
  if (can(user, 'dashboard:view', 'reports:view')) return '/dashboard'
  if (can(user, 'agents:edit')) return '/agentes'
  return '/ajustes'
}
