import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { NAV_ITEMS, type NavItem } from './navigation'

/** Ítems del menú a los que el perfil actual tiene acceso. */
export function useNavItems(): NavItem[] {
  const { user } = useAuth()
  return NAV_ITEMS.filter((item) => can(user, ...item.anyOf))
}
