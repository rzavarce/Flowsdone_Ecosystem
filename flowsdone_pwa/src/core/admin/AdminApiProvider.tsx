import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '@/core/auth/useAuth'
import { ApiError } from '@/core/http/apiFetch'
import type { AdminApi } from './AdminApi'
import { AdminApiContext } from './AdminApiContext'
import { createAdminApi } from './createAdminApi'
import { shouldRetry } from './retry'

/** Props de {@link AdminApiProvider}. */
export interface AdminApiProviderProps {
  children: ReactNode
  /** Adaptador a usar; por defecto el que indique `VITE_AUTH_MODE`. Inyectable en tests. */
  api?: AdminApi
}

const isUnauthorized = (error: unknown) => error instanceof ApiError && error.status === 401

/**
 * Vigila la caché: un 401 en cualquier consulta o mutación significa sesión
 * vencida, así que cierra la sesión local y `RequireAuth` lleva al login. Y
 * vacía la caché cuando cambia la persona autenticada, para que la siguiente
 * sesión nunca vea datos de la anterior.
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

/** Provee la API admin y la caché de datos (TanStack Query). */
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
