import { cn } from '@/lib/cn'
import { initials } from '@/lib/initials'

/** Props de {@link Avatar}. */
export interface AvatarProps {
  name: string
  className?: string
}

/** Círculo con las iniciales sobre el gradiente de marca del template activo. */
export function Avatar({ name, className }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-flex size-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white',
        className,
      )}
      style={{ backgroundImage: 'var(--gradient-brand)' }}
    >
      {initials(name)}
    </span>
  )
}
