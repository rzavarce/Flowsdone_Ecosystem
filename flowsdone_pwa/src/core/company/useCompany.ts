import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { createCompanyApi } from './createCompanyApi'

/**
 * Datos de facturación del tenant del usuario logueado (pensado para
 * `client`). `data` es `null` (no error) si todavía no se cargó nada -
 * ver `GET /me/billing-profile`.
 */
export function useCompany() {
  const [api] = useState(() => createCompanyApi())
  return useQuery({ queryKey: ['my-company'], queryFn: () => api.getMyCompany() })
}
