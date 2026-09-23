import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '@/core/auth/useAuth'
import { ApiError } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import { AdminApiContext } from './AdminApiContext'
import { createAdminApi } from './createAdminApi'
import { shouldRetry } from './retry'

/** Props for {@link AdminApiProvider}. */
export interface AdminApiProviderProps {
  children: ReactNode
  /** Adapter to use; defaults to whichever `VITE_AUTH_MODE` selects. Injectable in tests. */
  api?: AdminApi
}

/** Whether an error is a 401 response from the admin API. */
const isUnauthorized = (error: unknown) => error instanceof ApiError && error.status === 401

/**
 * Watches the cache: a 401 on any query or mutation means the session has
 * expired, so it logs out locally and `RequireAuth` redirects to login. It
 * also clears the cache whenever the authenticated user changes, so the next
 * session never sees the previous one's data.
 */
function SessionGuard() {
  const client = useQueryClient()
  const { user, logout } = useAuth()

  useEffect(() => {
    const onEvent = (event: { type: string; action?: { type: string; error?: unknown } }) => {
      if (event.type === 'updated' && event.action?.type === 'error' && isUnauthorized(event.action.error)) {
        void logout()
      }
    }
    const unsubscribeQueries = client.getQueryCache().subscribe(onEvent)
    const unsubscribeMutations = client.getMutationCache().subscribe(onEvent)
    return () => {
      unsubscribeQueries()
      unsubscribeMutations()
    }
  }, [client, logout])

  const userId = user?.id
  useEffect(() => {
    client.clear()
  }, [client, userId])

  return null
}

/** Provides the admin API and the data cache (TanStack Query). */
export function AdminApiProvider({ children, api }: AdminApiProviderProps) {
  const [adapter] = useState<AdminApi>(() => api ?? createAdminApi())
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: shouldRetry, refetchOnWindowFocus: false } },
      }),
  )

  return (
    <AdminApiContext value={adapter}>
      <QueryClientProvider client={client}>
        <SessionGuard />
        {children}
      </QueryClientProvider>
    </AdminApiContext>
  )
}
