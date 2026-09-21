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

/** Segundos que el token de verificación queda visible antes de ocultarse solo. */
const REVEAL_SECONDS = 30

/**
 * Integraciones de plataforma: las credenciales de la app de cada proveedor
 * (Meta, X, TikTok, Twilio), compartidas por todos los tenants. Solo admin.
 *
 * Los secretos guardados nunca se muestran. La única excepción es el token de
 * verificación del webhook de Meta, que hace falta pegar en el panel de Meta y
 * que se oculta solo a los {@link REVEAL_SECONDS} s.
 */
export function PlatformIntegrations() {
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
        title="Integraciones de plataforma"
        description="Credenciales de la app de cada proveedor, compartidas por todos los tenants. Se configuran una sola vez."
      />
      <div className="space-y-3 p-5">
        <Alert tone="info">
          Estas credenciales firman y verifican los webhooks de <strong>todos</strong> los clientes. Los secretos guardados
          no se pueden volver a ver; solo se pueden reemplazar.
        </Alert>

        {apps.isLoading ? (
          <Spinner label="Cargando integraciones" className="py-8" />
        ) : apps.error ? (
          <Alert tone="danger">
            <p>No se pudieron cargar las integraciones: {describeError(apps.error)}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => void apps.refetch()}>
              Reintentar
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
                        <Badge tone={isConfigured ? 'success' : 'neutral'}>{isConfigured ? 'Configurada' : 'Sin configurar'}</Badge>
                      </p>
                      <p className="mt-0.5 text-sm text-muted">{app.description}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {app.provider === 'meta' && isConfigured && (
                        <Button variant="ghost" size="sm" onClick={showToken} disabled={reveal.isPending}>
                          <Eye className="size-4" aria-hidden="true" />
                          Ver token de verificación
                        </Button>
                      )}
                      <Button variant="secondary" size="sm" onClick={() => setEditing(app)} aria-label={`${isConfigured ? 'Reemplazar' : 'Configurar'} ${app.label}`}>
                        {isConfigured ? 'Reemplazar' : 'Configurar'}
                      </Button>
                      {isConfigured && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            remove.reset()
                            setRemoving(app)
                          }}
                          aria-label={`Quitar ${app.label}`}
                        >
                          Quitar
                        </Button>
                      )}
                    </div>
                  </div>

                  {app.provider === 'meta' && token !== null && (
                    <div className="mt-3 rounded-xl bg-surface-muted p-3">
                      <p className="text-xs text-muted">Pégalo en el panel de Meta como "Verify token". Se oculta solo en {REVEAL_SECONDS} s.</p>
                      <div className="mt-2 flex items-center gap-2">
                        <code className="min-w-0 flex-1 truncate rounded-lg bg-surface px-3 py-2 font-mono text-xs" aria-label="Token de verificación">
                          {token || '(sin token)'}
                        </code>
                        <Button variant="secondary" size="sm" onClick={copyToken} disabled={!token}>
                          {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                          {copied ? 'Copiado' : 'Copiar'}
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
        title={removing ? `Quitar ${removing.label}` : ''}
        description="Los webhooks de este proveedor dejarán de verificarse: los mensajes entrantes de todos los tenants se ignorarán hasta que vuelvas a configurarlo."
        confirmLabel="Quitar credenciales"
        pending={remove.isPending}
        error={remove.error ? describeError(remove.error) : null}
        onConfirm={confirmRemove}
        onCancel={() => setRemoving(null)}
      />
    </Card>
  )
}
