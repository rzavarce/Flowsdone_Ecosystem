import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/core/auth/useAuth'
import { Spinner } from '@/components/ui/Spinner'

/** Only lets the request through with a session; without one, redirects to /login, remembering the destination. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spinner fullScreen label="Cargando sesión" />
  if (status === 'anonymous') return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <>{children}</>
}
