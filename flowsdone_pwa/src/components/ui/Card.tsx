import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

/** Container with a border and soft shadow; the base for dashboard panels. */
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('rounded-card border border-border bg-surface shadow-card', className)}
      {...props}
    />
  )
}

/** Props for {@link CardHeader}. */
export interface CardHeaderProps {
  title: string
  description?: string
  /** Right-aligned content (filters, actions). */
  action?: ReactNode
}

/** Standard Card header: title, optional subtitle, and action. */
export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5 sm:px-6">
      <div className="min-w-0">
        <h3 className="truncate text-lg font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  )
}
