import { createContext } from 'react'
import type { Credentials, User } from './types'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

/** Valor expuesto por {@link AuthProvider}. */
export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  login: (credentials: Credentials) => Promise<User>
  logout: () => Promise<void>
  /**
   * Vuelve a pedir el usuario al servidor (sus tenants pueden haber cambiado).
   * No cierra la sesión si falla: un 401 ya lo gestiona la capa de datos.
   */
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
