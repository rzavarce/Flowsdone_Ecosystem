import { useContext } from 'react'
import type { AdminApi } from './AdminApi'
import { AdminApiContext } from './AdminApiContext'

/**
 * Accede al adaptador de la API admin.
 *
 * @throws Error si se usa fuera de `<AdminApiProvider>`.
 */
export function useAdminApi(): AdminApi {
  const api = useContext(AdminApiContext)
  if (!api) throw new Error('useAdminApi debe usarse dentro de <AdminApiProvider>')
  return api
}
