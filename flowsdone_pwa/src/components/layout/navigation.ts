import { LayoutDashboard, MessageSquare, Plug, Settings, Workflow, type LucideIcon } from 'lucide-react'

/** Entrada del menú principal (sidebar y barra inferior comparten esta lista). */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/conversaciones', label: 'Conversaciones', icon: MessageSquare },
  { to: '/canales', label: 'Canales', icon: Plug },
  { to: '/workflows', label: 'Workflows', icon: Workflow },
  { to: '/ajustes', label: 'Ajustes', icon: Settings },
]
