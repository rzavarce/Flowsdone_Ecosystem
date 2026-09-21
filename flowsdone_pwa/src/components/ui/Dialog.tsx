import { X } from 'lucide-react'
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'

/** Props de {@link Dialog}. */
export interface DialogProps {
  open: boolean
  /** Se llama al pulsar Escape, la X o el fondo. */
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  /** Botones de acción, alineados a la derecha al pie. */
  footer?: ReactNode
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Diálogo modal accesible.
 *
 * - `role="dialog"` + `aria-modal`, nombrado por su título y descripción.
 * - Al abrir enfoca el primer campo; Tab queda atrapado dentro; Escape cierra.
 * - Al cerrar devuelve el foco a quien lo abrió y restaura el scroll del fondo.
 * - Se pinta en un portal para que ningún `overflow` del layout lo recorte.
 */
export function Dialog({ open, onClose, title, description, children, footer }: DialogProps) {
  const titleId = useId()
  const descId = useId()
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    const panel = panelRef.current
    const first = panel?.querySelector<HTMLElement>('input, select, textarea')
    // Si algo dentro ya tomó el foco (p. ej. `autoFocus` en "Cancelar" de una
    // confirmación destructiva), se respeta; si no, primer campo o el propio panel.
    if (!panel?.contains(document.activeElement)) (first ?? panel)?.focus()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = overflow
      previouslyFocused?.focus?.()
    }
  }, [open])

  if (!open) return null

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      event.stopPropagation()
      onClose()
      return
    }
    if (event.key !== 'Tab') return
    const items = [...(panelRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])]
    if (items.length === 0) return
    const first = items[0]!
    const last = items[items.length - 1]!
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-lg flex-col rounded-card border border-border bg-surface shadow-2xl outline-none sm:max-h-[calc(100dvh-3rem)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description && (
              <p id={descId} className="mt-1 text-sm text-muted">
                {description}
              </p>
            )}
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Cerrar" className="-mt-1 -mr-2 shrink-0">
            <X className="size-5" aria-hidden="true" />
          </Button>
        </div>
        <div className="overflow-y-auto px-6 py-6">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-3 rounded-b-card border-t border-border bg-surface-muted/40 px-6 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
