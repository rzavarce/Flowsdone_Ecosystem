import { Building2 } from 'lucide-react'
import { useId } from 'react'
import { ALL_TENANTS } from '@/core/tenant/TenantContext'
import { useTenant } from '@/core/tenant/useTenant'
import { useTranslation } from 'react-i18next'

/**
 * Active tenant selector. With a single option (a client, or a manager of
 * only one tenant) it's rendered as a fixed label to give context instead.
 */
export function TenantSwitcher() {
  const { t } = useTranslation()
  const { tenants, canSelectAll, selectedId, current, select } = useTenant()
  const id = useId()

  if (tenants.length === 0) return null

  const single = tenants.length === 1 && !canSelectAll
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-lg border border-border px-3 text-sm shadow-theme-xs">
      <Building2 className="size-4 shrink-0 text-muted" aria-hidden="true" />
      {single ? (
        <span className="h-11 max-w-40 truncate py-3 font-medium">{current?.name}</span>
      ) : (
        <>
          <label htmlFor={id} className="sr-only">
            {t('layout.activeTenant')}
          </label>
          <select
            id={id}
            value={selectedId}
            onChange={(e) => select(e.target.value)}
            className="h-11 max-w-40 cursor-pointer truncate bg-transparent font-medium focus-visible:outline-none sm:max-w-56 [&>option]:bg-surface"
          >
            {canSelectAll && <option value={ALL_TENANTS}>{t('layout.allTenants')}</option>}
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </>
      )}
    </div>
  )
}
