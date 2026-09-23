import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateProject, useProjects } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'
import { StepFrame } from './StepFrame'
import { useTranslation } from 'react-i18next'

/**
 * Step 3: the project (creating it also creates its folder in the tenant's
 * Langflow). If the tenant already has one, the wizard works on it.
 */
export function ProjectStep({ tenantId, onDone, onBack }: { tenantId: string; onDone: (projectId: string) => void; onBack: () => void }) {
  const { t } = useTranslation()
  const projects = useProjects(tenantId)
  const create = useCreateProject()
  const [name, setName] = useState<string>(t('onboarding.project.defaultName'))
  const [error, setError] = useState<string | null>(null)
  if (projects.isPending) return <Spinner label={t('onboarding.loading')} className="py-16" />
  const existing = [...(projects.data ?? [])].sort((a, b) => a.name.localeCompare(b.name))[0]

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (existing) return onDone(existing.id)
    if (!name.trim() || !slugify(name)) return setError(t('common.nameRequired'))
    setError(null)
    try {
      const project = await create.mutateAsync({ tenant_id: tenantId, name: name.trim(), slug: slugify(name) })
      onDone(project.id)
    } catch {
      // El error queda en create.error.
    }
  }

  return (
    <StepFrame
      title={t('onboarding.steps.project')}
      description={t('onboarding.project.description')}
      onSubmit={submit}
      onBack={onBack}
      pending={create.isPending}
      error={error ?? (create.error ? describeError(create.error) : null)}
    >
      {existing ? (
        <Alert tone="success">{t('onboarding.project.existing', { name: existing.name })}</Alert>
      ) : (
        <Field label={t('common.name')} hint={slugify(name) || undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
      )}
    </StepFrame>
  )
}
