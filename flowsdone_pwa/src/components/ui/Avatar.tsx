import { useState } from 'react'
import { cn } from '@/lib/cn'
import { initials } from '@/lib/initials'

/** Props for {@link Avatar}. */
export interface AvatarProps {
  name: string
  /** Photo URL; falls back to the initials if missing or if it fails to load. */
  src?: string | null
  className?: string
}

/** Profile photo, or a circle with initials over the active template's brand gradient. */
export function Avatar({ name, src, className }: AvatarProps) {
  const [failed, setFailed] = useState<string | null>(null)
  const base = 'inline-flex size-9 shrink-0 items-center justify-center overflow-hidden rounded-full'
  if (src && failed !== src) {
    return (
      <img
        src={src}
        alt=""
        aria-hidden="true"
        onError={() => setFailed(src)}
        className={cn(base, 'bg-surface-muted object-cover', className)}
      />
    )
  }
  return (
    <span
      aria-hidden="true"
      className={cn(base, 'text-xs font-semibold text-white', className)}
      style={{ backgroundImage: 'var(--gradient-brand)' }}
    >
      {initials(name)}
    </span>
  )
}
