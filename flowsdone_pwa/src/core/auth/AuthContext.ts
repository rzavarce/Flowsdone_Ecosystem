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
  /** Canjea el link de activación, crea la contraseña y deja la sesión iniciada. */
  activateAccount: (token: string, password: string) => Promise<User>
  /** Pide el email de "olvidé mi contraseña" (nunca revela si la cuenta existe). */
  requestPasswordReset: (email: string) => Promise<void>
  /** Canjea el link de recuperación, fija la contraseña nueva y deja la sesión iniciada. */
  resetPassword: (token: string, password: string) => Promise<User>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
