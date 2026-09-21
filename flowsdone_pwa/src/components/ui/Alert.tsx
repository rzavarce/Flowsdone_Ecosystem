import { CircleAlert, CircleCheck, Info } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

type Tone = 'danger' | 'success' | 'info'

const STYLES: Record<Tone, { box: string; icon: typeof Info }> = {
  danger: { box: 'bg-danger/10 text-danger', icon: CircleAlert },
  success: { box: 'bg-success/10 text-success', icon: CircleCheck },
  info: { box: 'bg-accent text-primary-ink', icon: Info },
}

/** Props de {@link Alert}. */
export interface AlertProps {
  tone?: Tone
  children: ReactNode
  className?: string
}

/** Mensaje destacado. `danger` se anuncia como alerta; el resto como aviso de estado. */
export function Alert({ tone = 'info', children, className }: AlertProps) {
  const { box, icon: Icon } = STYLES[tone]
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-sm', box, className)}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0">{children}</div>
    </div>
  )
}
