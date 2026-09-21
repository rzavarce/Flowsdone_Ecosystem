import { cn } from '@/lib/cn'

/** Isotipo + nombre. `showName` en false deja solo el isotipo (sidebar colapsada). */
export function Logo({ showName = true, className }: { showName?: boolean; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span
        className="inline-flex size-9 items-center justify-center rounded-xl text-primary-foreground shadow-sm"
        style={{ backgroundImage: 'var(--gradient-brand)' }}
        aria-hidden="true"
      >
        <svg viewBox="0 0 64 64" className="size-5" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round">
          <path d="M14 20h36M14 32h26M14 44h16" />
        </svg>
      </span>
      {showName && <span className="text-lg font-bold tracking-tight">Flowsdone</span>}
    </span>
  )
}
