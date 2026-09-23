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
  { to: '/conversations', label: 'Conversaciones', icon: MessageSquare, anyOf: ['conversations:manage'] },
  { to: '/channels', label: 'Canales', icon: Plug, anyOf: ['channels:manage'] },
  { to: '/tenants', label: 'Tenants', icon: Building2, anyOf: ['projects:manage'] },
  { to: '/users', label: 'Usuarios', icon: Users, anyOf: ['users:manage'] },
  { to: '/agents', label: 'Agentes', icon: Bot, anyOf: ['agents:edit'] },
  { to: '/company', label: 'Mi empresa', icon: Store, anyOf: ['company:view'] },
  { to: '/settings', label: 'Ajustes', icon: Settings, anyOf: ['settings:view'] },
]
