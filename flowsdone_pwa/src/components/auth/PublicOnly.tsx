import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { Spinner } from '@/components/ui/Spinner'

/**
 * Para pantallas públicas (login): si ya hay sesión, reenvía al destino que
 * se intentó abrir o, si no lo hay, a la página de inicio del perfil.
 */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spinner fullScreen label="Cargando sesión" />
  if (status === 'authenticated' && user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : homePathFor(user)} replace />
  }
  return <>{children}</>
}
