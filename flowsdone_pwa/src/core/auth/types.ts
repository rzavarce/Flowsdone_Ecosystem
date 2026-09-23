/** Platform profiles. `consultant`: a client's external consultant, scoped
 * to reports - created from Users the same way as `botmaster`/`tenant_manager`,
 * but never touches the admin API (same scope as `client`). */
export type Role = 'admin' | 'tenant_manager' | 'botmaster' | 'client' | 'consultant'

/** All known roles, in the order forms and selects should present them. */
export const ROLES: readonly Role[] = ['admin', 'tenant_manager', 'botmaster', 'client', 'consultant']

/**
 * Capabilities the UI can require. Deliberately granular: routes and the menu
 * ask for a permission, never a role, so adding or moving capabilities
 * between profiles happens in a single place (`ROLE_PERMISSIONS`).
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

/** A client organization on the platform; the unit of data isolation. */
export interface Tenant {
  id: string
  name: string
}

/** An authenticated user. `tenants` are the tenants they have access to. */
export interface User {
  id: string
  name: string
  email: string
  role: Role
  tenants: Tenant[]
}

/** Login credentials submitted from the login form. */
export interface Credentials {
  email: string
  password: string
}
