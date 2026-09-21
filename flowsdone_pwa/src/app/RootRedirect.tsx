import { Navigate } from 'react-router-dom'
import { Spinner } from '@/components/ui/Spinner'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'

/**
 * Ruta raíz (`/`): sin sesión lleva al login; con sesión, a la página de
 * inicio del perfil. No muestra contenido propio.
 */
export function RootRedirect() {
  const { status, user } = useAuth()
  if (status === 'loading') return <Spinner fullScreen label="Cargando sesión" />
  return <Navigate to={status === 'authenticated' && user ? homePathFor(user) : '/login'} replace />
}
