import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import type { CrmIntegrationWithSecrets } from '@/core/admin/types'
import { useTranslation } from 'react-i18next'

/** One labelled value with a copy button. */
function CopyRow({ label, value }: { label: string; value: string }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Sin portapapeles (http o permisos): el valor sigue visible para copiarlo a mano.
    }
  }

  return (
    <div>
      <p className="text-sm text-muted">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg bg-surface-muted px-3 py-2 font-mono text-xs">{value}</code>
        <Button variant="secondary" size="sm" onClick={copy} aria-label={t('integrations.secrets.copy', { name: label })}>
          {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
        </Button>
      </div>
    </div>
  )
}

/** Props for {@link CrmSecretsDialog}. */
export interface CrmSecretsDialogProps {
  integration: CrmIntegrationWithSecrets
  onClose: () => void
}

/**
 * Shows a CRM integration's secrets and API URLs right after it is created or
 * re-keyed: the gateway never returns them again, so they must be copied now.
 */
export function CrmSecretsDialog({ integration, onClose }: CrmSecretsDialogProps) {
  const { t } = useTranslation()
  return (
    <Dialog
      open
      onClose={onClose}
      title={t('integrations.secrets.title')}
      description={t('integrations.secrets.description')}
      footer={<Button onClick={onClose}>{t('integrations.secrets.done')}</Button>}
    >
      <div className="space-y-4">
        <Alert tone="info">{t('integrations.secrets.onlyNow')}</Alert>
        <CopyRow label={t('integrations.secrets.signingSecret')} value={integration.signing_secret} />
        <CopyRow label={t('integrations.secrets.apiKey')} value={integration.api_key} />
        <CopyRow label={t('integrations.replyUrl')} value={integration.reply_url} />
        <CopyRow label={t('integrations.closeUrl')} value={integration.close_url} />
      </div>
    </Dialog>
  )
}
