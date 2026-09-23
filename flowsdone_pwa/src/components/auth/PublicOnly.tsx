import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { Spinner } from '@/components/ui/Spinner'
import { useTranslation } from 'react-i18next'

/**
 * For public screens (login): if a session already exists, redirects to the
 * destination that was originally requested, or to the profile's home page
 * if there wasn't one.
 */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spinner fullScreen label={t('common.loadingSession')} />
  if (status === 'authenticated' && user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from !== '/login' ? from : homePathFor(user)} replace />
  }
  return <>{children}</>
}
