import { Navigate } from 'react-router-dom'
import { Spinner } from '@/components/ui/Spinner'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { useTranslation } from 'react-i18next'

/**
 * Root route (`/`): without a session it goes to login; with a session, to
 * the profile's home page. Renders no content of its own.
 */
export function RootRedirect() {
  const { t } = useTranslation()
  const { status, user } = useAuth()
  if (status === 'loading') return <Spinner fullScreen label={t('common.loadingSession')} />
  return <Navigate to={status === 'authenticated' && user ? homePathFor(user) : '/login'} replace />
}
