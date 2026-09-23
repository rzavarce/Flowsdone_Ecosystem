import { Check, Copy, Eye, KeyRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { ConfirmDialog } from '@/components/ui/ConfirmDialog'
import { Spinner } from '@/components/ui/Spinner'
import { useChannelApps, useDeleteChannelApp, useRevealChannelApp } from '@/core/admin/hooks'
import { describeError } from '@/core/http/describeError'
import { CHANNEL_APPS, type ChannelAppConfig } from './channelApps'
import { ChannelAppDialog } from './ChannelAppDialog'
import { Trans, useTranslation } from 'react-i18next'

/** Seconds the verification token stays visible before it hides itself. */
const REVEAL_SECONDS = 30

/**
 * Platform integrations: each provider's app credentials (Meta, X, TikTok,
 * Twilio), shared across all tenants. Admin only.
 *
 * Saved secrets are never shown. The one exception is Meta's webhook
 * verification token, which needs to be pasted into Meta's panel and hides
 * itself after {@link REVEAL_SECONDS} s.
 */
export function PlatformIntegrations() {
  const { t } = useTranslation()
  const apps = useChannelApps()
  const remove = useDeleteChannelApp()
  const reveal = useRevealChannelApp()
  const [editing, setEditing] = useState<ChannelAppConfig | null>(null)
  const [removing, setRemoving] = useState<ChannelAppConfig | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => () => clearTimeout(timer.current), [])

  const configured = new Set(apps.data?.filter((a) => a.has_credentials).map((a) => a.provider))

  async function showToken() {
    try {
      const credentials = await reveal.mutateAsync('meta')
      // Solo se conserva el token de verificación; los demás secretos se descartan.
      setToken(typeof credentials.webhook_verify_token === 'string' ? credentials.webhook_verify_token : '')
      clearTimeout(timer.current)
      timer.current = setTimeout(() => setToken(null), REVEAL_SECONDS * 1000)
    } catch {
      // El error se muestra abajo (reveal.error).
    }
  }

  async function copyToken() {
    if (!token) return
    try {
      await navigator.clipboard.writeText(token)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Sin permiso de portapapeles: la persona puede seleccionarlo a mano.
    }
  }

  async function confirmRemove() {
    if (!removing) return
    try {
      await remove.mutateAsync(removing.provider)
      if (removing.provider === 'meta') setToken(null)
      setRemoving(null)
    } catch {
      // El error se muestra en el diálogo.
    }
  }

  return (
    <Card>
      <CardHeader
        title={t('settings.integrations.title')}
        description={t('settings.integrations.description')}
      />
      <div className="space-y-3 p-5">
        <Alert tone="info">
          <Trans i18nKey="settings.integrations.notice" components={{ strong: <strong /> }} />
        </Alert>

        {apps.isLoading ? (
          <Spinner label={t('settings.integrations.loading')} className="py-8" />
        ) : apps.error ? (
          <Alert tone="danger">
            <p>{t('settings.integrations.loadError', { error: describeError(apps.error) })}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => void apps.refetch()}>
              {t('common.retry')}
            </Button>
          </Alert>
        ) : (
          <ul className="divide-y divide-border rounded-xl border border-border">
            {CHANNEL_APPS.map((app) => {
              const isConfigured = configured.has(app.provider)
              return (
                <li key={app.provider} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 font-medium">
                        <KeyRound className="size-4 text-muted" aria-hidden="true" />
                        {app.label}
                        <Badge tone={isConfigured ? 'success' : 'neutral'}>{isConfigured ? t('settings.integrations.configured') : t('settings.integrations.notConfigured')}</Badge>
                      </p>
                      <p className="mt-0.5 text-sm text-muted">{app.description}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {app.provider === 'meta' && isConfigured && (
                        <Button variant="ghost" size="sm" onClick={showToken} disabled={reveal.isPending}>
                          <Eye className="size-4" aria-hidden="true" />
                          {t('settings.integrations.showToken')}
                        </Button>
                      )}
                      <Button variant="secondary" size="sm" onClick={() => setEditing(app)} aria-label={t(isConfigured ? 'settings.integrations.replaceItem' : 'settings.integrations.configureItem', { name: app.label })}>
                        {isConfigured ? t('settings.integrations.replace') : t('settings.integrations.configure')}
                      </Button>
                      {isConfigured && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            remove.reset()
                            setRemoving(app)
                          }}
                          aria-label={t('settings.integrations.removeItem', { name: app.label })}
                        >
                          {t('settings.integrations.remove')}
                        </Button>
                      )}
                    </div>
                  </div>

                  {app.provider === 'meta' && token !== null && (
                    <div className="mt-3 rounded-xl bg-surface-muted p-3">
                      <p className="text-xs text-muted">{t('settings.integrations.tokenHelp', { seconds: REVEAL_SECONDS })}</p>
                      <div className="mt-2 flex items-center gap-2">
                        <code className="min-w-0 flex-1 truncate rounded-lg bg-surface px-3 py-2 font-mono text-xs" aria-label={t('settings.integrations.tokenLabel')}>
                          {token || t('settings.integrations.noToken')}
                        </code>
                        <Button variant="secondary" size="sm" onClick={copyToken} disabled={!token}>
                          {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                          {copied ? t('settings.integrations.copied') : t('settings.integrations.copy')}
                        </Button>
                      </div>
                    </div>
                  )}
                  {app.provider === 'meta' && reveal.error && <Alert tone="danger" className="mt-3">{describeError(reveal.error)}</Alert>}
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {editing && <ChannelAppDialog app={editing} configured={configured.has(editing.provider)} onClose={() => setEditing(null)} />}

      <ConfirmDialog
        open={removing !== null}
        title={removing ? t('settings.integrations.removeItem', { name: removing.label }) : ''}
        description={t('settings.integrations.removeDescription')}
        confirmLabel={t('settings.integrations.removeConfirm')}
        pending={remove.isPending}
        error={remove.error ? describeError(remove.error) : null}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(null)}
      />
    </Card>
  )
}
