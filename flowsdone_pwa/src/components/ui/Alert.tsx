import { CircleAlert, CircleCheck, Info, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Tone = 'danger' | 'success' | 'info'

const STYLES: Record<Tone, { box: string; icon: typeof Info; dismiss: string }> = {
  danger: { box: 'bg-danger/10 text-danger', icon: CircleAlert, dismiss: 'hover:bg-danger/15' },
  success: { box: 'bg-success/10 text-success', icon: CircleCheck, dismiss: 'hover:bg-success/15' },
  info: { box: 'bg-accent text-primary-ink', icon: Info, dismiss: 'hover:bg-black/5' },
}

/** Props de {@link Alert}. */
export interface AlertProps {
  tone?: Tone
  children: ReactNode
  className?: string
  /**
   * Aviso puntual que se puede quitar sin más (p. ej. "se reenvió el email").
   * Omitir cuando el mensaje refleja un estado que sigue roto (la lista no
   * cargó, un campo sigue inválido): quitarlo ahí no arregla nada y esconde
   * información útil.
   */
  onDismiss?: () => void
}

/** Mensaje destacado. `danger` se anuncia como alerta; el resto como aviso de estado. */
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
