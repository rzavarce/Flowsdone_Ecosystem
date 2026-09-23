import { Compass } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { useTranslation } from 'react-i18next'

/** View for routes that don't exist. */
export function NotFoundPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('pages.notFound.title')} />
      <EmptyState
        icon={Compass}
        title={t('pages.notFound.heading')}
        description={t('pages.notFound.description')}
      />
      <p className="mt-4 text-center">
        <Link to="/dashboard" className="font-medium text-primary-ink hover:underline">
          {t('pages.notFound.back')}
        </Link>
      </p>
    </>
  )
}
