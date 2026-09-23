import { useState } from 'react'
import { useResendUserActivation, useUsers } from '@/core/admin/hooks'
import type { UserRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { useTranslation } from 'react-i18next'

/** Outcome of the last "resend activation" attempt, shown next to the button. */
export interface ResendFeedback {
  tone: 'success' | 'danger'
  message: string
}

/**
 * A tenant's `client` account (the one created with the tenant) and a
 * "resend activation email" action for it. Admin only: listing users is.
 *
 * @param tenantId - The tenant.
 * @param enabled - Whether to load users (false for non-admins).
 */
export function useClientAccount(tenantId: string, enabled = true) {
  const { t } = useTranslation()
  const users = useUsers(enabled)
  const resend = useResendUserActivation()
  const [feedback, setFeedback] = useState<ResendFeedback | null>(null)
  const account: UserRecord | undefined = users.data?.find((u) => u.role === 'client' && u.tenant_ids.includes(tenantId))

  async function resendActivation() {
    if (!account) return
    setFeedback(null)
    try {
      await resend.mutateAsync(account.id)
      setFeedback({ tone: 'success', message: t('users.resend.done', { email: account.email }) })
    } catch (err) {
      setFeedback({ tone: 'danger', message: describeError(err) })
    }
  }

  return { users, account, resendActivation, resending: resend.isPending, feedback, clearFeedback: () => setFeedback(null) }
}
