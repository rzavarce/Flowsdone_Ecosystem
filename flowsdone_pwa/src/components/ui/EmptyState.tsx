import type { LucideIcon } from 'lucide-react'
import { Card } from './Card'

/** Props de {@link EmptyState}. */
export interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
}

/** Panel de "próximamente"/sin datos para secciones aún no implementadas. */
export function EmptyState({ icon: Icon, title, description }: EmptyStateProps) {
  return (
    <Card className="flex flex-col items-center px-6 py-16 text-center">
      <span className="mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-accent text-primary-ink">
        <Icon className="size-7" aria-hidden="true" />
      </span>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>
    </Card>
  )
}
