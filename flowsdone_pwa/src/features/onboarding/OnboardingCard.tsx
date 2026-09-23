import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/Alert'
import { Card, CardHeader } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useOnboarding } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import { OnboardingChecklist } from './OnboardingChecklist'
import { ResendClientActivation } from './ResendClientActivation'
import { useTranslation } from 'react-i18next'

/**
 * The tenant's onboarding checklist in its detail (admin/tenant_manager),
 * with a link back into the wizard where it was left (admin only: the
 * wizard creates tenants and assigns plans).
 */
export function OnboardingCard({ tenantId, canResume }: { tenantId: string; canResume: boolean }) {
  const { t } = useTranslation()
  const status = useOnboarding(tenantId)
  return (
    <Card>
      <CardHeader
        title={t('onboarding.card.title')}
        description={t('onboarding.card.description')}
        action={
          canResume &&
          status.data &&
          status.data.next_step !== 'summary' && (
            <Link
              to={`/onboarding?tenant=${tenantId}`}
              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg bg-cta px-3.5 text-sm font-medium text-cta-foreground"
            >
              {t('onboarding.resume')}
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          )
        }
      />
      <div className="p-5 pt-2 sm:px-6">
        {status.isPending ? (
          <Spinner label={t('onboarding.loading')} />
        ) : status.isError ? (
          <Alert tone="danger">{describeError(status.error)}</Alert>
        ) : (
          <OnboardingChecklist
            checks={status.data.checks}
            actions={canResume ? { client_account: <ResendClientActivation tenantId={tenantId} /> } : {}}
          />
        )}
      </div>
    </Card>
  )
}
