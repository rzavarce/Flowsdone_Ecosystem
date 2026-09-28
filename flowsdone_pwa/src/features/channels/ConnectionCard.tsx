import { Check, Code, Copy, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import type { ChannelConnection } from '@/core/admin/types'
import { CHANNEL_TYPES } from './channelTypes'
import { webchatSnippet } from './webchat'
import { useTranslation } from 'react-i18next'

/** Props for {@link ConnectionCard}. */
export interface ConnectionCardProps {
  connection: ChannelConnection
  /** Context to show under the name (tenant/project). */
  projectLabel: string
  agentName: string
  onEdit: (connection: ChannelConnection) => void
  onDelete: (connection: ChannelConnection) => void
}

/** Popup with the web chat's snippet and a copy button. */
function WebchatSnippetDialog({ snippet, onClose }: { snippet: string; onClose: () => void }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Sin permiso de portapapeles: el texto sigue visible para copiarlo a mano.
    }
  }

  return (
    <Dialog
      open
      onClose={onClose}
      title={t('channels.webchat.snippet')}
      description={t('channels.webchat.snippetHint')}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t('common.close')}
          </Button>
          <Button onClick={() => void copy()}>
            {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
            {copied ? t('channels.webchat.copied') : t('channels.webchat.copy')}
          </Button>
        </>
      }
    >
      <pre className="overflow-auto rounded-lg bg-surface-muted p-4 font-mono text-xs leading-relaxed whitespace-pre">{snippet}</pre>
    </Dialog>
  )
}

/**
 * Card for a connected channel: name, type, status, project/agent and actions.
 * Identifiers, credentials and settings are only shown in the edit form.
 */
export function ConnectionCard({ connection, projectLabel, agentName, onEdit, onDelete }: ConnectionCardProps) {
  const { t } = useTranslation()
  const config = CHANNEL_TYPES[connection.channel_type]
  const Icon = config.icon
  const name = connection.display_name || config.label
  const active = connection.status === 'active'
  const snippet = connection.channel_type === 'webchat' ? webchatSnippet(connection) : null
  const [showCode, setShowCode] = useState(false)

  return (
    <Card className="flex flex-col p-5 transition hover:border-primary/40">
      <div className="flex items-start gap-3">
        <span className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary-ink">
          <Icon className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-semibold">{name}</h2>
          <p className="truncate text-sm text-muted">{config.label}</p>
        </div>
        <Badge tone={active ? 'success' : 'warning'}>{active ? t('common.active') : t('common.inactive')}</Badge>
      </div>

      <dl className="mt-4 space-y-1.5 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">{t('common.project')}</dt>
          <dd className="min-w-0 truncate">{projectLabel}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">{t('common.agent')}</dt>
          <dd className="min-w-0 truncate">{agentName}</dd>
        </div>
      </dl>

      <div className="mt-5 flex justify-end gap-2 border-t border-border pt-4">
        {snippet && (
          <Button variant="secondary" size="sm" onClick={() => setShowCode(true)} aria-label={t('channels.webchat.snippet')} className="mr-auto">
            <Code className="size-4" aria-hidden="true" />
            {t('channels.webchat.showCode')}
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={() => onEdit(connection)} aria-label={t('common.editItem', { name })}>
          <Pencil className="size-4" aria-hidden="true" />
          {t('common.edit')}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(connection)} aria-label={t('common.deleteItem', { name })}>
          <Trash2 className="size-4" aria-hidden="true" />
          {t('common.delete')}
        </Button>
      </div>
      {snippet && showCode && <WebchatSnippetDialog snippet={snippet} onClose={() => setShowCode(false)} />}
    </Card>
  )
}
