import { Check, Copy, Link2, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { Spinner } from '@/components/ui/Spinner'
import { useCreateWebchatShare, useRevokeWebchatShare, useWebchatShares } from '@/core/admin/hooks'
import type { Agent, ShareLinkDays, WebchatShareLink } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { cn } from '@/lib/cn'

/** Validity options, in the order shown; `null` (never expires) is the default. */
const DURATIONS: ShareLinkDays[] = [null, 7, 30]

/** i18n key of a validity option. */
const durationKey = (days: ShareLinkDays) => (days === null ? 'never' : days === 7 ? 'days7' : 'days30')

/** One share link: its URL to copy, its dates and a two-step revoke. */
function ShareLinkRow({ link, onRevoke, revoking }: { link: WebchatShareLink; onRevoke: () => void; revoking: boolean }) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const date = (iso: string) => new Date(iso).toLocaleDateString(currentLocale())

  async function copy() {
    try {
      await navigator.clipboard.writeText(link.url)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      // Sin permiso de portapapeles: el enlace sigue visible para copiarlo a mano.
    }
  }

  return (
    <li className="space-y-2 py-3">
      <div className="flex items-center gap-2">
        <input
          readOnly
          value={link.url}
          aria-label={t('agents.share.linkUrl')}
          onFocus={(event) => event.currentTarget.select()}
          className={cn(
            'h-9 min-w-0 flex-1 rounded-lg border border-border bg-surface-muted px-3 font-mono text-xs text-foreground/80',
            link.expired && 'line-through opacity-60',
          )}
        />
        <Button size="sm" variant="secondary" onClick={() => void copy()} disabled={link.expired}>
          {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
          {copied ? t('agents.share.copied') : t('agents.share.copy')}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{t('agents.share.createdOn', { date: date(link.created_at) })}</span>
        <span aria-hidden="true">·</span>
        {link.expired ? (
          <Badge tone="warning">{t('agents.share.expired')}</Badge>
        ) : (
          <span>{link.expires_at ? t('agents.share.expiresOn', { date: date(link.expires_at) }) : t('agents.share.noExpiry')}</span>
        )}
        <span className="ms-auto flex items-center gap-2">
          {confirming ? (
            <>
              <span className="text-foreground/80">{t('agents.share.revokeConfirm')}</span>
              <Button size="sm" variant="secondary" onClick={() => setConfirming(false)} disabled={revoking}>
                {t('common.cancel')}
              </Button>
              <Button size="sm" variant="danger" onClick={onRevoke} disabled={revoking}>
                {t('agents.share.revoke')}
              </Button>
            </>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
              <Trash2 className="size-4" aria-hidden="true" />
              {t('agents.share.revoke')}
            </Button>
          )}
        </span>
      </div>
    </li>
  )
}

/**
 * The agent's public links ("Share"): anyone with one can chat with the
 * agent from the demo page, without logging in, until it expires (7 or 30
 * days, or never) or is revoked here.
 */
export function ShareAgentDialog({ agent, onClose }: { agent: Agent; onClose: () => void }) {
  const { t } = useTranslation()
  const [days, setDays] = useState<ShareLinkDays>(null)
  const links = useWebchatShares(agent.id)
  const create = useCreateWebchatShare()
  const revoke = useRevokeWebchatShare()

  return (
    <Dialog
      open
      onClose={onClose}
      title={t('agents.share.title', { name: agent.name })}
      description={t('agents.share.description')}
      footer={
        <Button variant="secondary" onClick={onClose}>
          {t('common.close')}
        </Button>
      }
    >
      <div className="space-y-5">
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-foreground/80">{t('agents.share.validity')}</legend>
          <div role="radiogroup" aria-label={t('agents.share.validity')} className="grid gap-2 sm:grid-cols-3">
            {DURATIONS.map((option) => (
              <button
                key={durationKey(option)}
                type="button"
                role="radio"
                aria-checked={days === option}
                onClick={() => setDays(option)}
                className={cn(
                  'cursor-pointer rounded-xl border px-3 py-2 text-left text-sm transition',
                  days === option ? 'border-primary bg-primary/5 ring-2 ring-primary/30' : 'border-border hover:bg-surface-muted',
                )}
              >
                {t(`agents.share.durations.${durationKey(option)}`)}
              </button>
            ))}
          </div>
        </fieldset>
        <Button
          onClick={() => void create.mutateAsync({ agentId: agent.id, expiresInDays: days }).catch(() => {})}
          disabled={create.isPending}
        >
          <Link2 className="size-4" aria-hidden="true" />
          {t('agents.share.create')}
        </Button>
        {create.error && <Alert tone="danger">{t('agents.share.createError', { error: describeError(create.error) })}</Alert>}
        {revoke.error && <Alert tone="danger">{t('agents.share.revokeError', { error: describeError(revoke.error) })}</Alert>}

        <div>
          <h3 className="text-sm font-medium text-foreground/80">{t('agents.share.links')}</h3>
          {links.isPending ? (
            <Spinner label={t('agents.share.loading')} className="py-6" />
          ) : links.isError ? (
            <Alert tone="danger">{t('agents.share.loadError', { error: describeError(links.error) })}</Alert>
          ) : links.data.length === 0 ? (
            <p className="py-3 text-sm text-muted">{t('agents.share.empty')}</p>
          ) : (
            <ul className="divide-y divide-border" aria-label={t('agents.share.links')}>
              {links.data.map((link) => (
                <ShareLinkRow
                  key={link.id}
                  link={link}
                  revoking={revoke.isPending}
                  onRevoke={() => void revoke.mutateAsync({ agentId: agent.id, shareId: link.id }).catch(() => {})}
                />
              ))}
            </ul>
          )}
        </div>
        <p className="text-xs text-muted">{t('agents.share.notice')}</p>
      </div>
    </Dialog>
  )
}
