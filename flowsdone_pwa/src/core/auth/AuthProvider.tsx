import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { AuthApi } from './AuthApi'
import { AuthContext, type AuthContextValue, type AuthStatus } from './AuthContext'
import { createAuthApi } from './createAuthApi'
import type { Credentials, User } from './types'

/** Props for {@link AuthProvider}. */
export interface AuthProviderProps {
  children: ReactNode
  /** Adapter to use; defaults to whichever `VITE_AUTH_MODE` selects. Injectable in tests. */
  api?: AuthApi
}

/**
 * Keeps the session: attempts to restore it on mount and exposes login/logout.
 * While restoring, `status` is `loading` (guards show a spinner instead of
 * redirecting to /login by mistake).
 */
export function AuthProvider({ children, api }: AuthProviderProps) {
  const [client] = useState<AuthApi>(() => api ?? createAuthApi())
  const [session, setSession] = useState<{ status: AuthStatus; user: User | null }>({
    status: 'loading',
    user: null,
  })

  useEffect(() => {
    let active = true
    client
      .restore()
      .catch(() => null)
      .then((user) => {
        if (active) setSession({ status: user ? 'authenticated' : 'anonymous', user })
      })
    return () => {
      active = false
    }
  }, [client])

  const login = useCallback(
    async (credentials: Credentials) => {
      const user = await client.login(credentials)
      setSession({ status: 'authenticated', user })
      return user
    },
    [client],
  )

  const logout = useCallback(async () => {
    try {
      await client.logout()
    } catch {
      // Mejor esfuerzo: si el servidor no confirma, igual se cierra la sesión local.
    }
    setSession({ status: 'anonymous', user: null })
  }, [client])

  const refreshUser = useCallback(async () => {
    const user = await client.restore().catch(() => null)
    // Un `null` puede ser un fallo de red transitorio: solo se actualiza con datos válidos.
    if (user) setSession({ status: 'authenticated', user })
  }, [client])

  const activateAccount = useCallback(
    async (token: string, password: string) => {
      const user = await client.activateAccount(token, password)
      setSession({ status: 'authenticated', user })
      return user
    },
    [client],
  )

  const requestPasswordReset = useCallback(
    (email: string) => client.requestPasswordReset(email),
    [client],
  )

  const resetPassword = useCallback(
    async (token: string, password: string) => {
      const user = await client.resetPassword(token, password)
      setSession({ status: 'authenticated', user })
      return user
    },
    [client],
  )

  const value = useMemo<AuthContextValue>(
    () => ({ ...session, login, logout, refreshUser, activateAccount, requestPasswordReset, resetPassword }),
    [session, login, logout, refreshUser, activateAccount, requestPasswordReset, resetPassword],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
