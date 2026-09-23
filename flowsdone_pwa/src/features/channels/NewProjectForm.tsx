import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Field, Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateProject } from '@/core/admin/hooks'
import type { Project } from '@/core/admin/types'
import type { Tenant } from '@/core/auth/types'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'
import { useTranslation } from 'react-i18next'

/** Props for {@link NewProjectForm}. */
export interface NewProjectFormProps {
  /** Tenants it can be created under (a single one = no selector). */
  tenants: Tenant[]
  defaultTenantId?: string
  onCreated: (project: Project) => void
}

/**
 * Minimal project creation form, so there's no dead end when a tenant
 * doesn't have any project yet (a channel always hangs off a project).
 */
export function NewProjectForm({ tenants, defaultTenantId, onCreated }: NewProjectFormProps) {
  const { t } = useTranslation()
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
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-dashed border-border p-4" aria-label={t('tenants.projects.new')}>
      <p className="text-sm text-muted">
        {t('channels.newProject.help')}
      </p>
      {tenants.length > 1 && (
        <Field label={t('common.tenant')}>
          <Select value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label={t('channels.newProject.name')}>
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('tenants.projects.namePlaceholder')} />
      </Field>
      <Field label={t('common.slug')} hint={t('common.slugHint')}>
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
        {create.isPending ? t('common.creating') : t('tenants.projects.create')}
      </Button>
    </form>
  )
}
