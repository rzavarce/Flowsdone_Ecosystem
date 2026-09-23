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
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold sm:text-2xl">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
