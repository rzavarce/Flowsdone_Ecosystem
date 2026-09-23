import { cn } from '@/lib/cn'

/** Props for {@link Spinner}. */
export interface SpinnerProps {
  /** Text for screen readers. */
  label: string
  /** Fills the whole screen and centers the indicator. */
  fullScreen?: boolean
  className?: string
}

/** Accessible loading indicator (`role="status"`). */
export function Spinner({ label, fullScreen, className }: SpinnerProps) {
  return (
    <div role="status" className={cn('flex items-center justify-center', fullScreen && 'min-h-dvh', className)}>
      <span className="size-8 animate-spin rounded-full border-4 border-border border-t-primary" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  )
}
