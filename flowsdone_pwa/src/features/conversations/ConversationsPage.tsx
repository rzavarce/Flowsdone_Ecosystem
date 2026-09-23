import { MessageSquare } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { EmptyState } from '@/components/ui/EmptyState'
import { useTranslation } from 'react-i18next'

/** Placeholder: conversations inbox (upcoming feature). */
export function ConversationsPage() {
  const { t } = useTranslation()
  return (
    <>
      <PageHeader title={t('nav.conversations')} description={t('conversations.description')} />
      <EmptyState
        icon={MessageSquare}
        title={t('common.comingSoon')}
        description={t('conversations.comingSoon')}
      />
    </>
  )
}
