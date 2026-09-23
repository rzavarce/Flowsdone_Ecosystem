import { X } from 'lucide-react'
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'
import { useTranslation } from 'react-i18next'

/** Props for {@link Dialog}. */
export interface DialogProps {
  open: boolean
  /** Called on Escape, the X button, or clicking the backdrop. */
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  /** Action buttons, right-aligned in the footer. */
  footer?: ReactNode
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Accessible modal dialog.
 *
 * - `role="dialog"` + `aria-modal`, named by its title and description.
 * - On open, focuses the first field; Tab is trapped inside; Escape closes it.
 * - On close, returns focus to whatever opened it and restores background scroll.
 * - Rendered into a portal so no layout `overflow` can clip it.
 */
export function Dialog({ open, onClose, title, description, children, footer }: DialogProps) {
  const { t } = useTranslation()
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-gray-400/50 p-4 backdrop-blur-md sm:p-6 dark:bg-black/60"
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
        className="flex max-h-[calc(100dvh-2rem)] w-full max-w-lg flex-col rounded-3xl border border-border bg-surface shadow-theme-xl outline-none sm:max-h-[calc(100dvh-3rem)]"
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-6 pb-2 sm:px-8 sm:pt-8">
          <div className="min-w-0">
            <h2 id={titleId} className="text-xl font-semibold sm:text-2xl">
              {title}
            </h2>
            {description && (
              <p id={descId} className="mt-1 text-sm text-muted">
                {description}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label={t('common.close')}
            className="-mt-1 -mr-2 shrink-0 rounded-full bg-surface-muted"
          >
            <X className="size-5" aria-hidden="true" />
          </Button>
        </div>
        <div className="overflow-y-auto px-6 py-5 sm:px-8">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-3 px-6 pt-2 pb-6 sm:px-8 sm:pb-8">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
