import { Bot, Building2, LayoutDashboard, MessageSquare, Plug, Settings, Store, Users, type LucideIcon } from 'lucide-react'
import type { Permission } from '@/core/auth/types'

/** Entrada del menú principal (sidebar y barra inferior comparten esta lista). */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** El ítem se muestra si el perfil tiene al menos uno de estos permisos. */
  anyOf: Permission[]
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, anyOf: ['dashboard:view', 'reports:view'] },
  { to: '/conversaciones', label: 'Conversaciones', icon: MessageSquare, anyOf: ['conversations:manage'] },
  { to: '/canales', label: 'Canales', icon: Plug, anyOf: ['channels:manage'] },
  { to: '/tenants', label: 'Tenants', icon: Building2, anyOf: ['projects:manage'] },
  { to: '/usuarios', label: 'Usuarios', icon: Users, anyOf: ['users:manage'] },
  { to: '/agentes', label: 'Agentes', icon: Bot, anyOf: ['agents:edit'] },
  { to: '/mi-empresa', label: 'Mi empresa', icon: Store, anyOf: ['company:view'] },
  { to: '/ajustes', label: 'Ajustes', icon: Settings, anyOf: ['settings:view'] },
]
