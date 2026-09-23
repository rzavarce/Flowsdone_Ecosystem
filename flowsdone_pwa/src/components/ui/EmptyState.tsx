import type { LucideIcon } from 'lucide-react'
import { Card } from './Card'

/** Props for {@link EmptyState}. */
export interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description: string
}

/** "Coming soon"/no-data panel for sections not yet implemented. */
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
