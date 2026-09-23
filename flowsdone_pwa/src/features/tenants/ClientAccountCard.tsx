import { Mail } from 'lucide-react'
import { Alert } from '@/components/ui/Alert'
import { Avatar } from '@/components/ui/Avatar'
import { Badge, type BadgeTone } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import type { UserRecord } from '@/core/admin/types'
import { useAdminApi } from '@/core/admin/useAdminApi'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { useClientAccount } from './useClientAccount'
import { useTranslation } from 'react-i18next'

const STATUS_TONE: Record<UserRecord['status'], BadgeTone> = { active: 'success', pending: 'warning', disabled: 'neutral' }

/**
 * The tenant's client account (admin only): who it is, whether they have
 * activated their access yet and when they last signed in, with "resend
 * activation email" while it is pending. Client accounts are hidden from the
 * Users screen, so this is where they are looked after.
 */
export function ClientAccountCard({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation()
  const api = useAdminApi()
  const { users, account, resendActivation, resending, feedback, clearFeedback } = useClientAccount(tenantId)

  return (
    <Card>
      <CardHeader title={t('tenants.clientAccount.title')} description={t('tenants.clientAccount.description')} />
      <div className="space-y-3 p-5 pt-4 sm:px-6">
        {users.isPending ? (
          <Spinner label={t('tenants.clientAccount.loading')} />
        ) : users.isError ? (
          <Alert tone="danger">{describeError(users.error)}</Alert>
        ) : !account ? (
          <p className="text-sm text-muted">{t('tenants.clientAccount.none')}</p>
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <Avatar name={account.name} src={api.userAvatarUrl(account)} className="size-10" />
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{account.name}</span>
                <Badge tone={STATUS_TONE[account.status]}>{t(`users.status.${account.status}`)}</Badge>
              </span>
              <span className="block truncate text-sm text-muted">{account.email}</span>
              <span className="block text-xs text-muted">
                {account.last_login_at
                  ? t('tenants.clientAccount.lastLogin', { date: new Date(account.last_login_at).toLocaleString(currentLocale(), { dateStyle: 'medium', timeStyle: 'short' }) })
                  : t('tenants.clientAccount.neverLogged')}
              </span>
            </span>
            {account.status === 'pending' && (
              <Button size="sm" variant="secondary" onClick={() => void resendActivation()} disabled={resending}>
                <Mail className="size-4" aria-hidden="true" />
                {resending ? t('users.resend.pending') : t('users.resend.action')}
              </Button>
            )}
          </div>
        )}
        {feedback && (
          <Alert tone={feedback.tone} onDismiss={clearFeedback}>
            {feedback.message}
          </Alert>
        )}
      </div>
    </Card>
  )
}
