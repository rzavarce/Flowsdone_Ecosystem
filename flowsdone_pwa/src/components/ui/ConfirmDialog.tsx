import { useState, type ReactNode } from 'react'
import { Button } from './Button'
import { Dialog } from './Dialog'
import { Field } from './Field'
import { Input } from './Input'

/** Props de {@link ConfirmDialog}. */
export interface ConfirmDialogProps {
  open: boolean
  title: string
  /** Consecuencias de la acción, en lenguaje claro. */
  description: string
  confirmLabel: string
  /** Mientras la acción está en curso: deshabilita los botones. */
  pending?: boolean
  /** Mensaje de error si la acción falló. */
  error?: string | null
  /** Detalle adicional (p. ej. qué se borrará en cascada). */
  children?: ReactNode
  /**
   * Si se indica, la persona debe escribir exactamente este texto para poder
   * confirmar (para acciones muy destructivas, como borrar un tenant).
   */
  requireText?: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Confirmación de una acción destructiva. El foco inicial cae en Cancelar (la
 * opción segura). Se monta solo mientras está abierta, así lo escrito para
 * confirmar nunca se arrastra de una apertura a la siguiente.
 */
export function ConfirmDialog(props: ConfirmDialogProps) {
  return props.open ? <ConfirmDialogOpen {...props} /> : null
}

function ConfirmDialogOpen({
  title,
  description,
  confirmLabel,
  pending,
  error,
  children,
  requireText,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState('')
  const armed = requireText === undefined || typed === requireText

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onCancel}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
            Cancelar
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={pending || !armed}>
            {pending ? 'Procesando…' : confirmLabel}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {children}
        {requireText !== undefined && (
          <Field label={`Escribe "${requireText}" para confirmar`}>
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
          </Field>
        )}
        {error ? (
          <p role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : (
          <p className="text-sm text-muted">Esta acción no se puede deshacer.</p>
        )}
      </div>
    </Dialog>
  )
}
