import type { ReactNode } from 'react'
import { can } from '@/core/auth/permissions'
import type { Permission } from '@/core/auth/types'
import { useAuth } from '@/core/auth/useAuth'
import { ForbiddenPage } from '@/features/ForbiddenPage'

/** Props de {@link RequirePermission}. */
export interface RequirePermissionProps {
  /** Basta con tener uno de estos permisos. */
  anyOf: Permission[]
  children: ReactNode
}

/** Muestra la vista solo si el perfil tiene permiso; si no, un 403. */
export function RequirePermission({ anyOf, children }: RequirePermissionProps) {
  const { user } = useAuth()
  return can(user, ...anyOf) ? <>{children}</> : <ForbiddenPage />
}
