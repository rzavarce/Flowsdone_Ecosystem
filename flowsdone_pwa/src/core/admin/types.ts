/** Tipos de la API admin del gateway (`/internal/admin/*`) tal como los usa la consola. */

import type { Role } from '@/core/auth/types'

/** Canales soportados por el gateway. */
export type ChannelType =
  | 'facebook'
  | 'instagram'
  | 'twitter'
  | 'whatsapp_evolution'
  | 'telegram'
  | 'tiktok'
  | 'voice'

/** Proveedores con una app compartida para toda la plataforma. */
export type ChannelAppProvider = 'meta' | 'twitter' | 'tiktok' | 'twilio'

/** Estado de ciclo de vida de tenants y proyectos. `suspended` corta el enrutado de sus canales sin borrar datos. */
export type LifecycleStatus = 'active' | 'suspended'

/** Un tenant tal como lo devuelve la API admin (el de la sesión, `core/auth`, solo trae id y nombre). */
export interface TenantRecord {
  id: string
  name: string
  slug: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateTenantInput {
  name: string
  slug: string
  /** Email del `client` que se crea junto al tenant (pending, activa por email). */
  client_email: string
  /** Nombre para mostrar de ese `client`. */
  client_name: string
}

/** Campos editables de un tenant; los omitidos no cambian. */
export interface UpdateTenantInput {
  name?: string
  slug?: string
  status?: LifecycleStatus
}

/** Datos de facturación de un tenant (1:1) - pura captura de datos, sin motor
 * de cobro detrás. Todo opcional: se completa gradualmente. */
export interface TenantBillingProfile {
  id: string
  tenant_id: string
  legal_name: string | null
  tax_id: string | null
  billing_email: string | null
  billing_contact_name: string | null
  billing_phone: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state_province: string | null
  postal_code: string | null
  country: string | null
  currency: string | null
  plan: string | null
  billing_cycle: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

/** Campos editables del perfil de facturación; los omitidos no cambian. */
export type UpdateTenantBillingInput = Partial<
  Omit<TenantBillingProfile, 'id' | 'tenant_id' | 'created_at' | 'updated_at'>
>

/** Campos editables de un proyecto; los omitidos no cambian. */
export interface UpdateProjectInput {
  name?: string
  slug?: string
  status?: LifecycleStatus
}

export interface Project {
  id: string
  tenant_id: string
  name: string
  slug: string
  status: string
}

export interface Agent {
  id: string
  project_id: string
  name: string
  langflow_flow_id: string
  is_default: boolean
  status: string
}

/** Un canal conectado de un cliente. Las credenciales nunca vuelven en claro. */
export interface ChannelConnection {
  id: string
  project_id: string
  agent_id: string
  channel_type: ChannelType
  external_id: string
  display_name: string | null
  has_credentials: boolean
  config: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

/** Credenciales compartidas de un proveedor; solo se sabe si están configuradas. */
export interface ChannelApp {
  id: string
  provider: ChannelAppProvider
  has_credentials: boolean
  config: Record<string, unknown>
  status: string
  created_at: string
  updated_at: string
}

export interface CreateProjectInput {
  tenant_id: string
  name: string
  slug: string
}

export interface CreateChannelConnectionInput {
  project_id: string
  agent_id: string
  channel_type: ChannelType
  external_id: string
  display_name?: string | null
  credentials?: Record<string, string>
}

/** Campos editables de una conexión; los omitidos no cambian. */
export interface UpdateChannelConnectionInput {
  agent_id?: string
  display_name?: string | null
  /** Si se envía REEMPLAZA las credenciales actuales. */
  credentials?: Record<string, string>
  status?: string
}

/** Estado de una cuenta de consola. `pending`: creada, esperando que active
 * su cuenta por el link que le llegó por email - no puede loguear todavía. */
export type UserAccountStatus = 'pending' | 'active' | 'disabled'

/** Un usuario de consola tal como lo devuelve la API admin. Nunca trae el hash. */
export interface UserRecord {
  id: string
  email: string
  name: string
  role: Role
  status: UserAccountStatus
  tenant_ids: string[]
  last_login_at: string | null
  created_at: string
  updated_at: string
}

/** Alta de un usuario. Sin password: se crea `pending` y activa por email
 * (ver `ProvisionUserUseCase` en el backend). */
export interface CreateUserInput {
  email: string
  name: string
  role: Role
  tenant_ids: string[]
}

/** Campos editables de un usuario; los omitidos no cambian. */
export interface UpdateUserInput {
  name?: string
  role?: Role
  status?: 'active' | 'disabled'
  tenant_ids?: string[]
}

/** Sesión para abrir Langflow como el usuario de un tenant. */
export interface LangflowSession {
  /**
   * URL del gateway que se carga en el iframe. Lleva un ticket de un solo uso que
   * caduca en segundos: hay que pedir una nueva cada vez que se monta el editor.
   * Vacía en el adaptador mock (no hay Langflow real).
   */
  url: string
}
