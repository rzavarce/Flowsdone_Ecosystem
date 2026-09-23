import { CircleAlert, CircleCheck, CircleDashed, CircleHelp, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { OnboardingCheck } from '@/core/admin/types'
import { cn } from '@/lib/cn'
import { useTranslation } from 'react-i18next'

const ICONS: Record<OnboardingCheck['status'], { icon: LucideIcon; tone: string }> = {
  ok: { icon: CircleCheck, tone: 'text-success' },
  warning: { icon: CircleAlert, tone: 'text-warning' },
  missing: { icon: CircleDashed, tone: 'text-danger' },
  unknown: { icon: CircleHelp, tone: 'text-muted' },
}

/** Where each item is fixed by hand. */
const FIX_AT: Record<OnboardingCheck['key'], string> = {
  billing: '/tenants',
  client_account: '/tenants',
  plan: '/tenants',
  project: '/tenants',
  agent: '/agents',
  openai_key: '/agents',
  channel: '/channels',
}

/**
 * A tenant's onboarding checklist: one line per item with its state, what
 * was found (plan name, project…) and, when something is pending, what to
 * do and a link to the section where it is done (plus any `actions` given
 * for that item).
 */
export function OnboardingChecklist({
  checks,
  actions = {},
}: {
  checks: OnboardingCheck[]
  /** Extra controls under an item (e.g. "resend activation" for the client account). */
  actions?: Partial<Record<OnboardingCheck['key'], ReactNode>>
}) {
  const { t, i18n } = useTranslation()
  return (
    <ul className="divide-y divide-border">
      {checks.map((check) => {
        const { icon: Icon, tone } = ICONS[check.status]
        const hintKey = `onboarding.checks.${check.key}.${check.status}`
        const hint = check.status !== 'ok' && i18n.exists(hintKey) ? t(hintKey as 'onboarding.checks.plan.missing') : null
        return (
          <li key={check.key} className="flex items-start gap-3 py-3 text-sm">
            <Icon className={cn('mt-0.5 size-5 shrink-0', tone)} aria-hidden="true" />
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">{t(`onboarding.checks.${check.key}.label`)}</span>
                <span className={cn('text-xs', tone)}>{t(`onboarding.status.${check.status}`)}</span>
                {check.status === 'ok' && check.detail && check.key !== 'openai_key' && (
                  <span className="truncate text-xs text-muted">· {check.detail}</span>
                )}
              </span>
              {hint && (
                <span className="mt-0.5 block text-xs text-muted">
                  {hint}{' '}
                  <Link to={FIX_AT[check.key]} className="font-medium text-primary-ink underline">
                    {t(`nav.${FIX_AT[check.key].slice(1)}` as 'nav.tenants')}
                  </Link>
                </span>
              )}
              {check.status !== 'ok' && actions[check.key]}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
