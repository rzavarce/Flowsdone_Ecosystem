import type { InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Base text field. Always pair it with a `label` or `aria-label`. */
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-10 w-full rounded-xl border border-border bg-surface-muted px-3 text-sm',
        'placeholder:text-muted focus-visible:bg-surface',
        className,
      )}
      {...props}
    />
  )
}
