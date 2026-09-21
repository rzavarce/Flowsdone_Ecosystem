import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

/** Contenedor con borde y sombra suave; base de los paneles del dashboard. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-card border border-border bg-surface shadow-card', className)}
      {...props}
    />
  )
}

/** Props de {@link CardHeader}. */
export interface CardHeaderProps {
  title: string
  description?: string
  /** Contenido alineado a la derecha (filtros, acciones). */
  action?: ReactNode
}

/** Cabecera estándar de una Card: título, subtítulo opcional y acción. */
export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 p-5 pb-0">
      <div className="min-w-0">
        <h3 className="truncate text-base font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}
