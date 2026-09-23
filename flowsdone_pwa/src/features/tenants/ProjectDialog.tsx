import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateProject, useUpdateProject } from '@/core/admin/hooks'
import type { Project, TenantRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'
import { useTranslation } from 'react-i18next'

/** Props for {@link ProjectDialog}. */
export interface ProjectDialogProps {
  tenant: TenantRecord
  /** `null` = create a project under `tenant`; a project = edit it. */
  project: Project | null
  onClose: () => void
}

const FORM_ID = 'project-form'

/** Create and edit a tenant's project. The slug is derived from the name until it's touched. */
export function ProjectDialog({ tenant, project, onClose }: ProjectDialogProps) {
  const { t } = useTranslation()
  const editing = project !== null
  const create = useCreateProject()
  const update = useUpdateProject()
  const [name, setName] = useState(project?.name ?? '')
  const [slug, setSlug] = useState(project?.slug ?? '')
  const [slugTouched, setSlugTouched] = useState(editing)
  const [submitted, setSubmitted] = useState(false)

  const effectiveSlug = slugTouched ? slug : slugify(name)
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  const errors = {
    name: name.trim() ? '' : t('common.nameRequired'),
    slug: effectiveSlug ? '' : t('common.slugRequired'),
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (errors.name || errors.slug) return
    try {
      if (editing) await update.mutateAsync({ id: project.id, patch: { name: name.trim(), slug: effectiveSlug } })
      else await create.mutateAsync({ tenant_id: tenant.id, name: name.trim(), slug: effectiveSlug })
      onClose()
    } catch {
      // El error queda en create.error / update.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={editing ? t('tenants.projects.edit') : t('tenants.projects.new')}
      description={t('tenants.projects.dialogDescription', { name: tenant.name })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : editing ? t('common.saveChanges') : t('tenants.projects.create')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label={t('common.name')} error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('tenants.projects.namePlaceholder')} />
        </Field>
        <Field label={t('common.slug')} hint={t('tenants.projects.slugHint')} error={submitted ? errors.slug : undefined}>
          <Input
            value={effectiveSlug}
            onChange={(e) => {
              setSlugTouched(true)
              setSlug(slugify(e.target.value))
            }}
            placeholder="atencion-al-cliente"
            autoComplete="off"
          />
        </Field>
        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
