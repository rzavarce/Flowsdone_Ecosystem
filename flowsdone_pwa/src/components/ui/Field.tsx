import { cloneElement, useId, type ReactElement, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Props for {@link Field}. */
export interface FieldProps {
  label: string
  /** Brief help text below the control. */
  hint?: string
  /** Validation error; announced to screen readers. */
  error?: string
  /** The control (Input, Select…). Receives `id` and `aria-describedby` automatically. */
  children: ReactElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>
}

/** Label + control + hint/error, with the ARIA attributes wired up. */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {cloneElement(children, { id, 'aria-describedby': describedBy, 'aria-invalid': error ? true : undefined })}
      {error ? (
        <p id={`${id}-error`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${id}-hint`} className="text-xs text-muted">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

/** Native `<select>` styled like the console's fields (accessible and mobile-friendly). */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'h-10 w-full cursor-pointer rounded-xl border border-border bg-surface-muted px-3 text-sm',
        'focus-visible:bg-surface disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}
