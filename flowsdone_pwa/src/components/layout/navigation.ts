import { Bot, Building2, LayoutDashboard, MessageSquare, Plug, Settings, Store, Users, type LucideIcon } from 'lucide-react'
import type { Permission } from '@/core/auth/types'

/** Main menu entry (sidebar and bottom bar share this list). */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** The item is shown if the profile has at least one of these permissions. */
  anyOf: Permission[]
}

/** Main navigation menu, in display order, filtered per profile by {@link useNavItems}. */
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
