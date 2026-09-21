import { Button } from './Button'
import { Dialog } from './Dialog'

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
  onConfirm: () => void
  onCancel: () => void
}

/** Confirmación de una acción destructiva. El foco inicial cae en Cancelar (la opción segura). */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  pending,
  error,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={pending ? () => {} : onCancel}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={pending} autoFocus>
            Cancelar
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={pending}>
            {pending ? 'Procesando…' : confirmLabel}
          </Button>
        </>
      }
    >
      {error ? (
        <p role="alert" className="rounded-xl bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : (
        <p className="text-sm text-muted">Esta acción no se puede deshacer.</p>
      )}
    </Dialog>
  )
}
