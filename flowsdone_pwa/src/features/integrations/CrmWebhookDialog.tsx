import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useCreateCrmIntegration, useUpdateCrmIntegration } from '@/core/admin/hooks'
import type { CrmIntegration, CrmIntegrationWithSecrets } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { useTranslation } from 'react-i18next'

const FORM_ID = 'crm-webhook-form'

/** Props for {@link CrmWebhookDialog}. */
export interface CrmWebhookDialogProps {
  projectId: string
  /** The integration to edit; null to create one. */
  integration: CrmIntegration | null
  /** Called with the new integration (and its secrets) after creating it. */
  onCreated: (integration: CrmIntegrationWithSecrets) => void
  onClose: () => void
}

/** Connects a project to its CRM through the generic webhook, or changes its URL. */
export function CrmWebhookDialog({ projectId, integration, onCreated, onClose }: CrmWebhookDialogProps) {
  const { t } = useTranslation()
  const create = useCreateCrmIntegration()
  const update = useUpdateCrmIntegration()
  const [url, setUrl] = useState(String(integration?.config.url ?? ''))
  const [submitted, setSubmitted] = useState(false)
  const pending = create.isPending || update.isPending
  const error = create.error ?? update.error
  // The gateway has the final word (https and public addresses only, outside
  // the hosts allowed for local testing); here only the shape is checked.
  const invalid = !/^https?:\/\/\S+$/.test(url.trim())

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
    if (invalid) return
    try {
      if (integration) {
        await update.mutateAsync({ id: integration.id, patch: { config: { url: url.trim() } } })
        onClose()
      } else {
        onCreated(await create.mutateAsync({ project_id: projectId, provider: 'generic_webhook', config: { url: url.trim() } }))
      }
    } catch {
      // El error queda en create.error / update.error.
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={integration ? t('integrations.webhook.editTitle') : t('integrations.webhook.connectTitle')}
      description={t('integrations.webhook.dialogDescription')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : integration ? t('common.save') : t('integrations.webhook.connect')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        <Field
          label={t('integrations.webhook.url')}
          hint={t('integrations.webhook.urlHint')}
          error={submitted && invalid ? t('integrations.webhook.urlInvalid') : undefined}
        >
          <Input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://crm.miempresa.com/webhooks/flowsdone" autoComplete="off" />
        </Field>
        {error && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}
