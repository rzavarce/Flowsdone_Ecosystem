import { Building2 } from 'lucide-react'
import { useId } from 'react'
import { ALL_TENANTS } from '@/core/tenant/TenantContext'
import { useTenant } from '@/core/tenant/useTenant'

/**
 * Selector del tenant activo. Con una sola opción (cliente, gestor de un
 * único tenant) se muestra como etiqueta fija para dar contexto.
 */
export function TenantSwitcher() {
  const { tenants, canSelectAll, selectedId, current, select } = useTenant()
  const id = useId()

  if (tenants.length === 0) return null

  const single = tenants.length === 1 && !canSelectAll
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-xl bg-surface-muted px-3 text-sm">
      <Building2 className="size-4 shrink-0 text-muted" aria-hidden="true" />
      {single ? (
        <span className="h-10 max-w-40 truncate py-2.5 font-medium">{current?.name}</span>
      ) : (
        <>
          <label htmlFor={id} className="sr-only">
            Tenant activo
          </label>
          <select
            id={id}
            value={selectedId}
            onChange={(e) => select(e.target.value)}
            className="h-10 max-w-40 cursor-pointer truncate bg-transparent font-medium focus-visible:outline-none sm:max-w-56"
          >
            {canSelectAll && <option value={ALL_TENANTS}>Todos los tenants</option>}
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
