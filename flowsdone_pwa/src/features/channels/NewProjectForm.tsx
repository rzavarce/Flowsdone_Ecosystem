import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateProject } from '@/core/admin/hooks'
import type { Project } from '@/core/admin/types'
import type { Tenant } from '@/core/auth/types'
import { describeError } from './describeError'
import { slugify } from './channelTypes'

/** Props de {@link NewProjectForm}. */
export interface NewProjectFormProps {
  /** Tenants entre los que se puede crear (uno solo = sin selector). */
  tenants: Tenant[]
  defaultTenantId?: string
  onCreated: (project: Project) => void
}

/**
 * Alta mínima de un proyecto, para no dejar un callejón sin salida cuando un
 * tenant todavía no tiene ninguno (un canal siempre cuelga de un proyecto).
 */
export function NewProjectForm({ tenants, defaultTenantId, onCreated }: NewProjectFormProps) {
  const create = useCreateProject()
  const [tenantId, setTenantId] = useState(defaultTenantId ?? tenants[0]?.id ?? '')
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)

  const effectiveSlug = slugTouched ? slug : slugify(name)
  const valid = tenantId && name.trim() && effectiveSlug

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid) return
    const project = await create.mutateAsync({ tenant_id: tenantId, name: name.trim(), slug: effectiveSlug }).catch(() => null)
    if (project) onCreated(project)
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-dashed border-border p-4" aria-label="Nuevo proyecto">
      <p className="text-sm text-muted">
        Un canal siempre pertenece a un proyecto. Crea el primero para continuar.
      </p>
      {tenants.length > 1 && (
        <Field label="Tenant">
          <Select value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label="Nombre del proyecto">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Atención al cliente" />
      </Field>
      <Field label="Identificador (slug)" hint="Minúsculas, números y guiones.">
        <Input
          value={effectiveSlug}
          onChange={(e) => {
            setSlugTouched(true)
            setSlug(slugify(e.target.value))
          }}
          placeholder="atencion-al-cliente"
        />
      </Field>
      {create.error && <Alert tone="danger">{describeError(create.error)}</Alert>}
      <Button type="submit" size="sm" disabled={!valid || create.isPending}>
        {create.isPending ? 'Creando…' : 'Crear proyecto'}
      </Button>
    </form>
  )
}
