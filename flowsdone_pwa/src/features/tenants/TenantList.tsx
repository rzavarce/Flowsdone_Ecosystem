import { Building2 } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/cn'
import { summarize, type TenantEntry } from './useTenantsView'
import { useTranslation } from 'react-i18next'

/** Props for {@link TenantList}. */
export interface TenantListProps {
  entries: TenantEntry[]
  selectedId: string
  onSelect: (id: string) => void
}

/** List of tenants (single selection) with their status and what each one contains. */
export function TenantList({ entries, selectedId, onSelect }: TenantListProps) {
  const { t } = useTranslation()
  return (
    <Card className="overflow-hidden">
      <ul aria-label={t('nav.tenants')} className="divide-y divide-border">
        {entries.map(({ tenant, projects, agents, channels }) => {
          const selected = tenant.id === selectedId
          return (
            <li key={tenant.id}>
              <button
                type="button"
                onClick={() => onSelect(tenant.id)}
                aria-current={selected ? 'true' : undefined}
                className={cn(
                  'flex w-full cursor-pointer items-start gap-3 px-4 py-3.5 text-left transition',
                  selected ? 'bg-primary/10' : 'hover:bg-surface-muted',
                )}
              >
                <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-surface-muted text-primary-ink">
                  <Building2 className="size-4.5" aria-hidden="true" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{tenant.name}</span>
                    {tenant.status !== 'active' && <Badge tone="warning">{t('common.suspended')}</Badge>}
                  </span>
                  <span className="block truncate font-mono text-xs text-muted">{tenant.slug}</span>
                  <span className="mt-1 block text-xs text-muted">{summarize({ projects: projects.length, agents, channels })}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}
