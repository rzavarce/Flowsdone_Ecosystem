import { createContext } from 'react'
import type { Credentials, User } from './types'

/** Session lifecycle: `loading` while restoring, then `authenticated` or `anonymous`. */
export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

/** Value exposed by {@link AuthProvider}. */
export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  login: (credentials: Credentials) => Promise<User>
  logout: () => Promise<void>
  /**
   * Re-fetches the user from the server (their tenants may have changed).
   * Doesn't log out on failure: a 401 is already handled by the data layer.
   */
  refreshUser: () => Promise<void>
  /** Redeems the activation link, sets the password and leaves the session logged in. */
  activateAccount: (token: string, password: string) => Promise<User>
  /** Requests the "forgot my password" email (never reveals whether the account exists). */
  requestPasswordReset: (email: string) => Promise<void>
  /** Redeems the recovery link, sets the new password and leaves the session logged in. */
  resetPassword: (token: string, password: string) => Promise<User>
}

/** React context carrying the current {@link AuthContextValue}; `null` outside `<AuthProvider>`. */
export const AuthContext = createContext<AuthContextValue | null>(null)
