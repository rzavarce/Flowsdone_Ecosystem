import { useContext } from 'react'
import { AuthContext, type AuthContextValue } from './AuthContext'

/**
 * Accede a la sesión actual.
 *
 * @throws Error si se usa fuera de `<AuthProvider>`.
 */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
