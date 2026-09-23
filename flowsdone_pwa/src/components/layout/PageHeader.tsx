import type { ReactNode } from 'react'

/** Props for {@link PageHeader}. */
export interface PageHeaderProps {
  title: string
  description?: string
  /** Right-aligned actions (page buttons). */
  actions?: ReactNode
}

/** Page title with description and actions; the sole `<h1>` on each view. */
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
