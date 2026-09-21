import type { ReactNode } from 'react'

/** Props de {@link PageHeader}. */
export interface PageHeaderProps {
  title: string
  description?: string
  /** Acciones alineadas a la derecha (botones de la página). */
  actions?: ReactNode
}

/** Título de página con descripción y acciones; único `<h1>` de cada vista. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1 text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
