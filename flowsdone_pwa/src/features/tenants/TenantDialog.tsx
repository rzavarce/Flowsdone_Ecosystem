import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateTenant, useUpdateTenant } from '@/core/admin/hooks'
import type { TenantRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { slugify } from '@/lib/slug'

/** Props de {@link TenantDialog}. */
export interface TenantDialogProps {
  /** `null` = crear un tenant; un tenant = editarlo. */
  tenant: TenantRecord | null
  onClose: () => void
  /** Se llama con el tenant creado (para seleccionarlo). */
  onSaved?: (tenant: TenantRecord) => void
}

const FORM_ID = 'tenant-form'

/** Alta y edición de un tenant (solo admin). El slug se deriva del nombre hasta que se toca. */
export function TenantDialog({ tenant, onClose, onSaved }: TenantDialogProps) {
  const editing = tenant !== null
  const create = useCreateTenant()
  const update = useUpdateTenant()
  const [name, setName] = useState(tenant?.name ?? '')
  const [slug, setSlug] = useState(tenant?.slug ?? '')
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
      const saved = editing
        ? await update.mutateAsync({ id: tenant.id, patch: { name: name.trim(), slug: effectiveSlug } })
        : await create.mutateAsync({ name: name.trim(), slug: effectiveSlug })
      onSaved?.(saved)
      onClose()
    } catch {
      // El error queda en create.error / update.error y se muestra abajo.
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={editing ? 'Editar tenant' : 'Nuevo tenant'}
      description={editing ? tenant.name : 'Un tenant es una organización cliente: agrupa sus proyectos, agentes y canales.'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear tenant'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field label="Nombre" error={submitted ? errors.name : undefined}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Clínica Vital" />
        </Field>
        <Field
          label="Identificador (slug)"
          hint={editing ? 'Se usa en comandos como create_user --tenant. Cambiarlo puede romper scripts que ya lo usen.' : 'Minúsculas, números y guiones. Debe ser único.'}
          error={submitted ? errors.slug : undefined}
        >
          <Input
            value={effectiveSlug}
            onChange={(e) => {
              setSlugTouched(true)
              setSlug(slugify(e.target.value))
            }}
            placeholder="clinica-vital"
            autoComplete="off"
          />
        </Field>
        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
