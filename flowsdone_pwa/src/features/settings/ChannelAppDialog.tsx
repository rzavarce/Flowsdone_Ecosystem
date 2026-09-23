import { useState, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useUpsertChannelApp } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import type { ChannelAppConfig } from './channelApps'
import { useTranslation } from 'react-i18next'

/** Props for {@link ChannelAppDialog}. */
export interface ChannelAppDialogProps {
  app: ChannelAppConfig
  /** If it already has credentials, saving REPLACES them (and the user is warned). */
  configured: boolean
  onClose: () => void
}

const FORM_ID = 'channel-app-form'

/**
 * Configures a provider's shared credentials.
 *
 * The gateway never returns saved secrets, so editing means rewriting all of
 * them: `PUT` replaces the whole set (except Meta's webhook verification
 * token, which is kept if a new one isn't sent).
 */
export function ChannelAppDialog({ app, configured, onClose }: ChannelAppDialogProps) {
  const { t } = useTranslation()
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
      title={configured ? t('settings.integrations.replaceTitle', { name: app.label }) : t('settings.integrations.configureItem', { name: app.label })}
      description={app.description}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={save.isPending}>
            {save.isPending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-5">
        {configured && (
          <Alert tone="info">
            {t('settings.integrations.replaceNotice')}
          </Alert>
        )}
        {app.fields.map((field) => (
          <Field
            key={field.key}
            label={field.label}
            hint={field.hint}
            error={submitted && missing.includes(field) ? t('common.fieldRequired', { field: field.label }) : undefined}
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
