import { Check } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Spinner } from '@/components/ui/Spinner'
import { useOnboarding, useTenants } from '@/core/admin/hooks'
import type { OnboardingStep } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { useTenant } from '@/core/tenant/useTenant'
import { cn } from '@/lib/cn'
import { AgentStep } from './AgentStep'
import { CompanyStep } from './CompanyStep'
import { OnboardingChecklist } from './OnboardingChecklist'
import { PlanStep } from './PlanStep'
import { ResendClientActivation } from './ResendClientActivation'
import { ProjectStep } from './ProjectStep'
import { StepFrame } from './StepFrame'
import { useTranslation } from 'react-i18next'

const STEPS: OnboardingStep[] = ['company', 'plan', 'project', 'agent', 'summary']

/** "Step n of 5" plus the list of steps, done ones checked. */
function Stepper({ current }: { current: OnboardingStep }) {
  const { t } = useTranslation()
  const index = STEPS.indexOf(current)
  return (
    <nav aria-label={t('onboarding.title')} className="mb-6">
      <p className="mb-3 text-sm text-muted">{t('onboarding.stepOf', { current: index + 1, total: STEPS.length })}</p>
      <ol className="flex flex-wrap gap-2">
        {STEPS.map((step, i) => (
          <li
            key={step}
            aria-current={i === index ? 'step' : undefined}
            className={cn(
              'flex items-center gap-2 rounded-full px-3 py-1.5 text-sm',
              i === index ? 'bg-primary text-white' : i < index ? 'bg-primary/10 text-primary-ink' : 'bg-surface-muted text-muted',
            )}
          >
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-white/20 text-xs font-semibold">
              {i < index ? <Check className="size-3.5" aria-hidden="true" /> : i + 1}
            </span>
            {t(`onboarding.steps.${step}`)}
          </li>
        ))}
      </ol>
    </nav>
  )
}

/**
 * New-client wizard (admin): company and billing -> plan -> project -> base
 * agent -> summary. Every step is saved when continuing; `?tenant=<id>`
 * resumes a client at the first step still to do, computed by the gateway
 * from what exists (`GET /tenants/{id}/onboarding`), so nothing half-done
 * can be lost or duplicated. Channels (WhatsApp included) are connected by
 * hand afterwards.
 */
export function OnboardingPage() {
  const { t } = useTranslation()
  const [params, setParams] = useSearchParams()
  const tenantId = params.get('tenant') ?? undefined
  const status = useOnboarding(tenantId)
  const tenants = useTenants()
  const { select } = useTenant()
  const navigate = useNavigate()
  // Paso y proyecto elegidos en esta visita; hasta entonces, al retomar, los
  // que calcula el gateway (primer paso pendiente), derivados en el render.
  const [chosenStep, setStep] = useState<OnboardingStep | null>(null)
  const [chosenProject, setProjectId] = useState<string | null>(null)
  const step: OnboardingStep | null = chosenStep ?? (tenantId ? (status.data?.next_step ?? null) : 'company')
  const projectId = chosenProject ?? status.data?.project_id ?? null

  const go = (next: OnboardingStep) => {
    setStep(next)
    if (next === 'summary') void status.refetch()
  }
  const header = <PageHeader title={t('onboarding.title')} description={t('onboarding.description')} />

  if (tenantId && step === null) {
    return (
      <>
        {header}
        {status.isError ? <Alert tone="danger">{describeError(status.error)}</Alert> : <Spinner label={t('onboarding.loading')} className="py-20" />}
      </>
    )
  }
  const current = step ?? 'company'
  const companyName = tenants.data?.find((x) => x.id === tenantId)?.name ?? ''

  return (
    <div>
      {header}
      <Stepper current={current} />
      {current === 'company' && (
        <CompanyStep
          tenantId={tenantId}
          onDone={(id) => {
            setParams({ tenant: id }, { replace: true })
            go('plan')
          }}
        />
      )}
      {current === 'plan' && tenantId && <PlanStep tenantId={tenantId} onBack={() => go('company')} onDone={() => go('project')} />}
      {current === 'project' && tenantId && (
        <ProjectStep
          tenantId={tenantId}
          onBack={() => go('plan')}
          onDone={(id) => {
            setProjectId(id)
            go('agent')
          }}
        />
      )}
      {current === 'agent' && projectId && (
        <AgentStep projectId={projectId} companyName={companyName} onBack={() => go('project')} onDone={() => go('summary')} />
      )}
      {current === 'summary' && tenantId && (
        <StepFrame
          title={t('onboarding.steps.summary')}
          description={t('onboarding.summary.description')}
          footer={
            <div className="flex flex-wrap justify-between gap-3 border-t border-border pt-5">
              <Button variant="secondary" onClick={() => go('agent')}>
                {t('onboarding.back')}
              </Button>
              <Button
                onClick={() => {
                  select(tenantId)
                  navigate('/tenants')
                }}
              >
                {t('onboarding.goToTenant')}
              </Button>
            </div>
          }
        >
          {status.isPending || status.isFetching ? (
            <Spinner label={t('onboarding.loading')} />
          ) : status.isError ? (
            <Alert tone="danger">{describeError(status.error)}</Alert>
          ) : (
            <OnboardingChecklist checks={status.data.checks} actions={{ client_account: <ResendClientActivation tenantId={tenantId} /> }} />
          )}
        </StepFrame>
      )}
    </div>
  )
}
