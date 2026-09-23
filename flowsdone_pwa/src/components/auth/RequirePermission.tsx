import type { ReactNode } from 'react'
import { can } from '@/core/auth/permissions'
import type { Permission } from '@/core/auth/types'
import { useAuth } from '@/core/auth/useAuth'
import { ForbiddenPage } from '@/features/ForbiddenPage'

/** Props for {@link RequirePermission}. */
export interface RequirePermissionProps {
  /** Having any one of these permissions is enough. */
  anyOf: Permission[]
  children: ReactNode
}

/** Renders the view only if the profile has permission; otherwise, a 403. */
export function RequirePermission({ anyOf, children }: RequirePermissionProps) {
  const { user } = useAuth()
  return can(user, ...anyOf) ? <>{children}</> : <ForbiddenPage />
}
