import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { useTranslation } from 'react-i18next'

type Tone = 'danger' | 'success' | 'info'

const STYLES: Record<Tone, { box: string; icon: typeof Info; dismiss: string }> = {
  danger: { box: 'border-danger/40 bg-danger/5 text-danger', icon: CircleAlert, dismiss: 'hover:bg-danger/15' },
  success: { box: 'border-success/40 bg-success/5 text-success', icon: CircleCheck, dismiss: 'hover:bg-success/15' },
  info: { box: 'border-primary/40 bg-primary/5 text-primary-ink', icon: Info, dismiss: 'hover:bg-primary/10' },
}

/** Props for {@link Alert}. */
export interface AlertProps {
  tone?: Tone
  children: ReactNode
  className?: string
  /**
   * One-off notice that can just be dismissed (e.g. "the email was resent").
   * Omit it when the message reflects a state that's still broken (the list
   * failed to load, a field is still invalid): dismissing it there fixes
   * nothing and hides useful information.
   */
  onDismiss?: () => void
}

/** Highlighted message. `danger` is announced as an alert; the rest as a status notice. */
export function Alert({ tone = 'info', children, className, onDismiss }: AlertProps) {
  const { t } = useTranslation()
  const { box, icon: Icon, dismiss } = STYLES[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-xl border px-4 py-3.5 text-sm', box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={t('common.dismissNotice')}
          className={cn('-my-1 -mr-1 inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-lg', dismiss)}
        >
          <X className="size-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}
