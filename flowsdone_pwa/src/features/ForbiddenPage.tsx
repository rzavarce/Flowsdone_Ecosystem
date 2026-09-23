import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { homePathFor } from '@/core/auth/permissions'
import { useAuth } from '@/core/auth/useAuth'
import { useTranslation } from 'react-i18next'

/** 403 view: the user is authenticated but their role doesn't include this section. */
export function ForbiddenPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <>
      <PageHeader title={t('pages.forbidden.title')} />
      <EmptyState
        icon={ShieldAlert}
        title={t('pages.forbidden.heading')}
        description={t('pages.forbidden.description')}
      />
      <p className="mt-4 text-center">
        <Link to={user ? homePathFor(user) : '/login'} className="font-medium text-primary-ink hover:underline">
          {t('pages.forbidden.home')}
        </Link>
      </p>
    </>
  )
}
