import { cloneElement, useId, type ReactElement, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

/** Props de {@link Field}. */
export interface FieldProps {
  label: string
  /** Ayuda breve bajo el control. */
  hint?: string
  /** Error de validación; se anuncia a lectores de pantalla. */
  error?: string
  /** El control (Input, Select…). Recibe `id` y `aria-describedby` automáticamente. */
  children: ReactElement<{ id?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>
}

/** Etiqueta + control + ayuda/error, con los atributos ARIA conectados. */
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

/** `<select>` nativo con el estilo de los campos de la consola (accesible y móvil-friendly). */
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
