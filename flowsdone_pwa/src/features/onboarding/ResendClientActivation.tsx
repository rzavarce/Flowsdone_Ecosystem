import { Mail } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useClientAccount } from '@/features/tenants/useClientAccount'
import { cn } from '@/lib/cn'
import { useTranslation } from 'react-i18next'

/**
 * "Resend activation" for the onboarding checklist's client-account item,
 * shown while the tenant's client account is still pending (admin only).
 */
export function ResendClientActivation({ tenantId }: { tenantId: string }) {
  const { t } = useTranslation()
  const { account, resendActivation, resending, feedback } = useClientAccount(tenantId)
  if (!account || account.status !== 'pending') return null
  return (
    <span className="mt-1.5 flex flex-wrap items-center gap-2">
      <Button size="sm" variant="secondary" onClick={() => void resendActivation()} disabled={resending}>
        <Mail className="size-4" aria-hidden="true" />
        {resending ? t('users.resend.pending') : t('users.resend.action')}
      </Button>
      {feedback && <span role="status" className={cn('text-xs', feedback.tone === 'success' ? 'text-success' : 'text-danger')}>{feedback.message}</span>}
    </span>
  )
}
