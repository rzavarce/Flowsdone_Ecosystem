import { cn } from '@/lib/cn'

/** Props de {@link Spinner}. */
export interface SpinnerProps {
  /** Texto para lectores de pantalla. */
  label: string
  /** Ocupa toda la pantalla y centra el indicador. */
  fullScreen?: boolean
  className?: string
}

/** Indicador de carga accesible (`role="status"`). */
export function Spinner({ label, fullScreen, className }: SpinnerProps) {
  return (
    <div role="status" className={cn('flex items-center justify-center', fullScreen && 'min-h-dvh', className)}>
      <span className="size-8 animate-spin rounded-full border-4 border-border border-t-primary" aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </div>
  )
}
