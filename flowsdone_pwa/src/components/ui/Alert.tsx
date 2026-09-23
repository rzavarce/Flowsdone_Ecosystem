import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Tone = 'danger' | 'success' | 'info'

const STYLES: Record<Tone, { box: string; icon: typeof Info; dismiss: string }> = {
  danger: { box: 'bg-danger/10 text-danger', icon: CircleAlert, dismiss: 'hover:bg-danger/15' },
  success: { box: 'bg-success/10 text-success', icon: CircleCheck, dismiss: 'hover:bg-success/15' },
  info: { box: 'bg-accent text-primary-ink', icon: Info, dismiss: 'hover:bg-black/5' },
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
  const { box, icon: Icon, dismiss } = STYLES[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm', box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">{children}</div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Quitar aviso"
          className={cn('-my-1 -mr-1 inline-flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-lg', dismiss)}
        >
          <X className="size-3.5" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}
