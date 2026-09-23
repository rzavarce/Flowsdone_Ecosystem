import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Semantic tones available for {@link Badge}. */
export type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-muted text-muted',
  primary: 'bg-primary/10 text-primary-ink dark:bg-primary/15',
  success: 'bg-success/10 text-success dark:bg-success/15',
  warning: 'bg-warning/15 text-warning',
  danger: 'bg-danger/10 text-danger dark:bg-danger/15',
}

/** Props for {@link Badge}. */
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone
}

/** Compact label for statuses (active channel, error, etc.). */
export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
      {...props}
    />
  )
}
