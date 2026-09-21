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

/** Props de {@link ProjectDialog}. */
export interface ProjectDialogProps {
  tenant: TenantRecord
  /** `null` = crear un proyecto en `tenant`; un proyecto = editarlo. */
  project: Project | null
  onClose: () => void
}

const FORM_ID = 'project-form'

/** Alta y edición de un proyecto de un tenant. El slug se deriva del nombre hasta que se toca. */
export function ProjectDialog({ tenant, project, onClose }: ProjectDialogProps) {
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
    name: name.trim() ? '' : 'El nombre es obligatorio.',
    slug: effectiveSlug ? '' : 'El identificador es obligatorio.',
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
      title={editing ? 'Editar proyecto' : 'Nuevo proyecto'}
      description={`Tenant: ${tenant.name}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear proyecto'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label="Nombre" error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Atención al cliente" />
        </Field>
        <Field label="Identificador (slug)" hint="Minúsculas, números y guiones. Único dentro del tenant." error={submitted ? errors.slug : undefined}>
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
