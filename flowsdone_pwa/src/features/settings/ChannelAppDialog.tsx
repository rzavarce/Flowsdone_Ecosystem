import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useUpsertChannelApp } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import type { ChannelAppConfig } from './channelApps'

/** Props de {@link ChannelAppDialog}. */
export interface ChannelAppDialogProps {
  app: ChannelAppConfig
  /** Si ya tiene credenciales, guardar las REEMPLAZA (y se avisa). */
  configured: boolean
  onClose: () => void
}

const FORM_ID = 'channel-app-form'

/**
 * Configura las credenciales compartidas de un proveedor.
 *
 * El gateway nunca devuelve los secretos guardados, así que al editar hay que
 * volver a escribirlos todos: `PUT` reemplaza el conjunto completo (salvo el
 * token de verificación de Meta, que se conserva si no se envía uno nuevo).
 */
export function ChannelAppDialog({ app, configured, onClose }: ChannelAppDialogProps) {
  const save = useUpsertChannelApp()
  const [values, setValues] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const missing = app.fields.filter((f) => f.required && !values[f.key]?.trim())

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (missing.length) return
    const credentials = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()))
    try {
      await save.mutateAsync({ provider: app.provider, credentials })
      onClose()
    } catch {
      // El error queda en save.error.
    }
  }

  return (
    <Dialog
      open
      onClose={save.isPending ? () => {} : onClose}
      title={configured ? `Reemplazar credenciales de ${app.label}` : `Configurar ${app.label}`}
      description={app.description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            Cancelar
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending}>
            {save.isPending ? 'Guardando…' : 'Guardar'}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        {configured && (
          <Alert tone="info">
            Ya hay credenciales guardadas y no se pueden mostrar. Al guardar se reemplazan por las que escribas aquí: vuelve
            a introducir todas.
          </Alert>
        )}
        {app.fields.map((field) => (
          <Field
            key={field.key}
            label={field.label}
            hint={field.hint}
            error={submitted && missing.includes(field) ? `${field.label} es obligatorio.` : undefined}
          >
            <Input
              type="password"
              value={values[field.key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
              autoComplete="off"
            />
          </Field>
        ))}
        {save.error && <Alert tone="danger">{describeError(save.error)}</Alert>}
      </form>
    </Dialog>
  )
}
