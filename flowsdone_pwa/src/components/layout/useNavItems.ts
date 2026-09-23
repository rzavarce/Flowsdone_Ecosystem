import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { NAV_ITEMS, type NavItem } from './navigation'

/** Menu items the current profile has access to. */
export function useNavItems(): NavItem[] {
  const { user } = useAuth()
  return NAV_ITEMS.filter((item) => can(user, ...item.anyOf))
}
