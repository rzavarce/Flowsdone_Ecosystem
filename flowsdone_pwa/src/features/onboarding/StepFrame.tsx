import type { FormEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useTranslation } from 'react-i18next'

/** Props for {@link StepFrame}. */
export interface StepFrameProps {
  title: string
  description: string
  children: ReactNode
  /** Submits the step; omit for steps without a form (the summary). */
  onSubmit?: (event: FormEvent) => void
  onBack?: () => void
  pending?: boolean
  /** Label shown on the submit button while `pending`. */
  pendingLabel?: string
  error?: string | null
  /** Replaces the default footer (the summary's own actions). */
  footer?: ReactNode
}

/**
 * Common layout of a wizard step: title, content, error and the footer with
 * "Back", "Finish later" (back to Tenants: everything saved so far stays)
 * and "Save and continue".
 */
export function StepFrame({ title, description, children, onSubmit, onBack, pending, pendingLabel, error, footer }: StepFrameProps) {
  const { t } = useTranslation()
  return (
    <Card className="p-5 sm:p-8">
      <form onSubmit={onSubmit} noValidate className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-muted">{description}</p>
        </div>
        {children}
        {error && <Alert tone="danger">{error}</Alert>}
        {footer ?? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
            <div className="flex gap-2">
              {onBack && (
                <Button variant="secondary" onClick={onBack} disabled={pending}>
                  {t('onboarding.back')}
                </Button>
              )}
              <Link to="/tenants" className="inline-flex h-11 items-center px-3 text-sm font-medium text-muted hover:text-foreground">
                {t('onboarding.later')}
              </Link>
            </div>
            <Button type="submit" disabled={pending}>
              {pending ? (pendingLabel ?? t('common.saving')) : t('onboarding.next')}
            </Button>
          </div>
        )}
      </form>
    </Card>
  )
}
