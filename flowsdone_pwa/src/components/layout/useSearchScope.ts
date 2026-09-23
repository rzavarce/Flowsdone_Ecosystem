import { can } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'

/** The permission-gated profile sections the search looks into. */
export function useSearchScope() {
  const { user } = useAuth()
  return {
    tenants: can(user, 'projects:manage'),
    conversations: can(user, 'conversations:manage'),
    users: can(user, 'users:manage'),
    agents: can(user, 'agents:edit'),
    channels: can(user, 'channels:manage'),
  }
}

/** Whether the current profile has anything to search (the top bar hides the box otherwise). */
export function useCanSearch(): boolean {
  return Object.values(useSearchScope()).some(Boolean)
}
