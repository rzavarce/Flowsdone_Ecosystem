import { Bot, Building2, LayoutDashboard, MessageSquare, Plug, Receipt, Settings, Store, Users, type LucideIcon } from 'lucide-react'
import type { Permission } from '@/core/auth/types'
import { i18n } from '@/core/i18n/i18n'

/** Main menu entry (sidebar and bottom bar share this list). */
export interface NavItem {
  to: string
  readonly label: string
  icon: LucideIcon
  /** The item is shown if the profile has at least one of these permissions. */
  anyOf: Permission[]
}

/** Builds an entry whose label is translated when read (follows language changes). */
const item = (to: string, key: string, icon: LucideIcon, anyOf: Permission[]): NavItem => ({
  to,
  icon,
  anyOf,
  get label() {
    return i18n.t(`nav.${key}` as 'nav.dashboard')
  },
})

/** Main navigation menu, in display order, filtered per profile by {@link useNavItems}. */
export const NAV_ITEMS: readonly NavItem[] = [
  item('/dashboard', 'dashboard', LayoutDashboard, ['dashboard:view', 'reports:view']),
  item('/conversations', 'conversations', MessageSquare, ['conversations:manage']),
  item('/channels', 'channels', Plug, ['channels:manage']),
  item('/tenants', 'tenants', Building2, ['projects:manage']),
  item('/users', 'users', Users, ['users:manage']),
  item('/agents', 'agents', Bot, ['agents:edit']),
  item('/company', 'company', Store, ['company:view']),
  item('/plans', 'plans', Receipt, ['platform:manage']),
  item('/settings', 'settings', Settings, ['settings:view']),
]
