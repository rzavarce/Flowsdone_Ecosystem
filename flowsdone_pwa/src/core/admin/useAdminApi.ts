import { useContext } from 'react'
import type { AdminApi } from './AdminApi'
import { AdminApiContext } from './AdminApiContext'

/**
 * Accesses the admin API adapter.
 *
 * @throws Error if used outside `<AdminApiProvider>`.
 */
export function useAdminApi(): AdminApi {
  const api = useContext(AdminApiContext)
  if (!api) throw new Error('useAdminApi debe usarse dentro de <AdminApiProvider>')
  return api
}
