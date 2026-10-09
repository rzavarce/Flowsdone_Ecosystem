import { UserRoundCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useStartCrmHandoff } from '@/core/admin/hooks'
import { ApiError } from '@/core/http/apiFetch'
import { describeError } from '@/core/http/describeError'
import { useTranslation } from 'react-i18next'

const FORM_ID = 'crm-handoff-form'

/** Props for {@link CrmHandoffButton}. */
export interface CrmHandoffButtonProps {
  conversationId: string
}

/**
 * Hands a live conversation over to its project's CRM: the bot stops
 * answering and a person continues from the CRM. The gateway refuses it if
 * the project has no active CRM integration or the conversation is no longer
 * live (its session expired).
 */
export function CrmHandoffButton({ conversationId }: CrmHandoffButtonProps) {
  const { t } = useTranslation()
  const start = useStartCrmHandoff()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await start.mutateAsync({ conversationId, reason: reason.trim() || undefined })
      setOpen(false)
    } catch {
      // El error se muestra en el diálogo.
    }
  }

  const errorText = (error: Error) => {
    if (error instanceof ApiError && error.status === 409) return t('conversations.handoff.noIntegration')
    if (error instanceof ApiError && error.status === 404) return t('conversations.handoff.notLive')
    return describeError(error)
  }

  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => { start.reset(); setOpen(true) }} disabled={start.isSuccess}>
        <UserRoundCheck className="size-4" aria-hidden="true" />
        {start.isSuccess ? t('conversations.handoff.done') : t('conversations.handoff.button')}
      </Button>
      {start.isSuccess && <Alert tone="success" className="mt-3">{t('conversations.handoff.success')}</Alert>}
      {open && (
        <Dialog
          open
          onClose={start.isPending ? () => {} : () => setOpen(false)}
          title={t('conversations.handoff.title')}
          description={t('conversations.handoff.description')}
          footer={
            <>
              <Button variant="secondary" onClick={() => setOpen(false)} disabled={start.isPending}>
                {t('common.cancel')}
              </Button>
              <Button type="submit" form={FORM_ID} disabled={start.isPending}>
                {start.isPending ? t('common.saving') : t('conversations.handoff.confirm')}
              </Button>
            </>
          }
        >
          <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
            <Field label={t('conversations.handoff.reason')} hint={t('conversations.handoff.reasonHint')}>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
            </Field>
            {start.error && <Alert tone="danger">{errorText(start.error)}</Alert>}
          </form>
        </Dialog>
      )}
    </>
  )
}
