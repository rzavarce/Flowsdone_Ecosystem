import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'icon'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-cta text-cta-foreground shadow-theme-xs hover:brightness-95 dark:hover:brightness-110',
  // "outline" de TailAdmin: borde interior del color de los campos.
  secondary: 'bg-surface text-foreground/85 shadow-theme-xs ring-1 ring-input ring-inset hover:bg-surface-muted hover:text-foreground',
  ghost: 'text-muted hover:bg-surface-muted hover:text-foreground',
  // text-background: el fondo de la app da buen contraste sobre el rojo en claro y en oscuro.
  danger: 'bg-danger text-background shadow-theme-xs hover:brightness-110',
}

const SIZES: Record<Size, string> = {
  sm: 'h-9 gap-1.5 px-3.5 text-sm',
  md: 'h-11 gap-2 px-5 text-sm',
  icon: 'size-10',
}

/** Props for {@link Button}. */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
}

/** Base button. For icon-only buttons, use `size="icon"` plus an `aria-label`. */
export function Button({ variant = 'primary', size = 'md', className, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center justify-center rounded-lg font-medium transition',
        'disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  )
}
