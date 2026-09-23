/** Perfiles de la plataforma. `consultant`: consultor de un cliente, acotado
 * a reportes - se crea desde Usuarios como `botmaster`/`tenant_manager`,
 * pero nunca toca el admin API (mismo alcance que `client`). */
export type Role = 'admin' | 'tenant_manager' | 'botmaster' | 'client' | 'consultant'

export const ROLES: readonly Role[] = ['admin', 'tenant_manager', 'botmaster', 'client', 'consultant']

/**
 * Capacidades que la UI puede exigir. Son granulares a propósito: las rutas y
 * el menú preguntan por un permiso, nunca por un rol, así que sumar o mover
 * capacidades entre perfiles se hace en un solo lugar (`ROLE_PERMISSIONS`).
 */
export type Permission =
  | 'dashboard:view' // dashboard operativo completo
  | 'reports:view' // gráficos y paneles de solo lectura
  | 'conversations:manage'
  | 'channels:manage'
  | 'agents:edit' // editor de agentes (Langflow embebido)
  | 'settings:view'
  | 'projects:manage' // pantalla Tenants: proyectos de los tenants propios (admin y gestor)
  | 'tenants:manage' // crear, editar, suspender y borrar tenants (solo admin)
  | 'platform:manage' // credenciales compartidas de proveedores (Meta, X, TikTok, Twilio)
  | 'users:manage' // pantalla Usuarios: alta/edición/borrado de admin, tenant_manager y botmaster (solo admin)
  | 'company:view' // "Mi empresa": datos de facturación del propio tenant, solo lectura (solo client)

/** Organización cliente de la plataforma; unidad de aislamiento de datos. */
export interface Tenant {
  id: string
  name: string
}

/** Usuario autenticado. `tenants` son los tenants a los que tiene acceso. */
export interface User {
  id: string
  name: string
  email: string
  role: Role
  tenants: Tenant[]
}

export interface Credentials {
  email: string
  password: string
}
