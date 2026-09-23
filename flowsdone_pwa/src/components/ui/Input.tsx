import type { InputHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Base text field. Always pair it with a `label` or `aria-label`. */
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-11 w-full rounded-lg border border-input bg-transparent px-4 text-sm shadow-theme-xs',
        'placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none',
        'disabled:cursor-not-allowed disabled:bg-surface-muted disabled:opacity-60',
        'aria-invalid:border-danger aria-invalid:focus-visible:ring-danger/15',
        className,
      )}
      {...props}
    />
  )
}
