import { useState, type ReactNode } from 'react'
import { Button } from './Button'
import { Dialog } from './Dialog'
import { Field } from './Field'
import { Input } from './Input'
import { useTranslation } from 'react-i18next'

/** Props for {@link ConfirmDialog}. */
export interface ConfirmDialogProps {
  open: boolean
  title: string
  /** Consequences of the action, in plain language. */
  description: string
  confirmLabel: string
  /** While the action is in progress: disables the buttons. */
  pending?: boolean
  /** Error message if the action failed. */
  error?: string | null
  /** Extra detail (e.g. what gets deleted along with it). */
  children?: ReactNode
  /**
   * If set, the user must type this exact text before they can confirm
   * (for highly destructive actions, like deleting a tenant).
   */
  requireText?: string
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Confirmation for a destructive action. Initial focus lands on Cancel (the
 * safe option). It only mounts while open, so anything typed to confirm
 * never carries over from one opening to the next.
 */
export function ConfirmDialog(props: ConfirmDialogProps) {
  return props.open ? <ConfirmDialogOpen {...props} /> : null
}

/** Renders the actual dialog contents; mounted only while {@link ConfirmDialog} is open. */
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
  const { t } = useTranslation()
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
            {t('common.cancel')}
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={pending || !armed}>
            {pending ? t('common.processing') : confirmLabel}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {children}
        {requireText !== undefined && (
          <Field label={t('common.typeToConfirm', { text: requireText })}>
            <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
          </Field>
        )}
        {error ? (
          <p role="alert" className="rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        ) : (
          <p className="text-sm text-muted">{t('common.irreversible')}</p>
        )}
      </div>
    </Dialog>
  )
}
