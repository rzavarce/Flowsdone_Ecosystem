import { ArrowLeft, Ban } from 'lucide-react'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Spinner } from '@/components/ui/Spinner'
import { useConversation } from '@/core/admin/billingHooks'
import type { ConversationMessage } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { channelLabel, kindLabel, unitLabel } from '@/features/billing/labels'
import { cn } from '@/lib/cn'
import { formatMoney, formatNumber } from '@/lib/money'
import { useTranslation } from 'react-i18next'

/** Date and time in the active language. */
const when = (iso: string) => new Date(iso).toLocaleString(currentLocale(), { dateStyle: 'medium', timeStyle: 'short' })

/** One transcript bubble: the contact on the left, the agent (or a person) on the right. */
function Bubble({ message }: { message: ConversationMessage }) {
  const { t } = useTranslation()
  const inbound = message.direction === 'inbound'
  return (
    <li className={cn('flex flex-col gap-1', inbound ? 'items-start' : 'items-end')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap',
          inbound ? 'rounded-bl-md bg-surface-muted' : 'rounded-br-md bg-primary/10 text-foreground dark:bg-primary/20',
        )}
      >
        {message.text}
      </div>
      <span className="text-xs text-muted">
        {t(`conversations.sender.${message.sender_type}`)} · {new Date(message.timestamp).toLocaleTimeString(currentLocale(), { timeStyle: 'short' })}
      </span>
      {!message.billable && (
        <span className="flex items-center gap-1 text-xs text-warning">
          <Ban className="size-3.5" aria-hidden="true" />
          {t('conversations.refused')}
        </span>
      )}
    </li>
  )
}

/** Props for {@link ConversationDetail}. */
export interface ConversationDetailProps {
  conversationId: string
  /** Shown on small screens, where the list and the detail don't fit side by side. */
  onBack: () => void
}

/**
 * One conversation: status and dates, the transcript (kept 6 months) and its
 * usage - tokens per model and, for admins only (the gateway strips it for
 * everyone else), what it cost Flowsdone.
 */
export function ConversationDetail({ conversationId, onBack }: ConversationDetailProps) {
  const { t } = useTranslation()
  const detail = useConversation(conversationId)

  if (detail.isPending) return <Spinner label={t('conversations.loading')} className="py-20" />
  if (detail.isError) return <Alert tone="danger">{describeError(detail.error)}</Alert>

  const { conversation: c, messages, usage } = detail.data
  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={onBack} className="lg:hidden">
        <ArrowLeft className="size-4" aria-hidden="true" />
        {t('conversations.back')}
      </Button>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-xl font-semibold">{c.contact}</h2>
            <p className="mt-0.5 text-sm text-muted">
              {channelLabel(c.channel_type)} · {t('conversations.messages', { count: c.inbound_count + c.outbound_count })}
            </p>
          </div>
          <Badge tone={c.status === 'open' ? 'success' : 'neutral'}>{t(`conversations.status.${c.status}`)}</Badge>
        </div>
        <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-muted">{t('conversations.startedAt')}</dt>
            <dd className="font-medium">{when(c.started_at)}</dd>
          </div>
          <div>
            <dt className="text-muted">{t('conversations.lastActivity')}</dt>
            <dd className="font-medium">{when(c.last_message_at)}</dd>
          </div>
        </dl>
        {c.close_reason && <p className="mt-3 text-xs text-muted">{t(`conversations.closeReason.${c.close_reason}`)}</p>}
      </Card>

      <Card>
        <CardHeader title={t('conversations.transcript')} />
        <div className="p-5 pt-4 sm:px-6">
          {messages.length === 0 ? (
            <p className="text-sm text-muted">{t('conversations.noMessages')}</p>
          ) : (
            <ol className="space-y-3" aria-label={t('conversations.transcript')}>
              {messages.map((m) => (
                <Bubble key={m.message_id} message={m} />
              ))}
            </ol>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader title={t('conversations.usage.title')} />
        <div className="space-y-4 p-5 pt-4 sm:px-6">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-muted">{t('conversations.usage.tokensIn')}</dt>
              <dd className="font-medium tabular-nums">{formatNumber(detail.data.llm_input_tokens)}</dd>
            </div>
            <div>
              <dt className="text-muted">{t('conversations.usage.tokensOut')}</dt>
              <dd className="font-medium tabular-nums">{formatNumber(detail.data.llm_output_tokens)}</dd>
            </div>
            <div>
              <dt className="text-muted">{t('conversations.usage.tokensCached')}</dt>
              <dd className="font-medium tabular-nums">{formatNumber(detail.data.llm_cached_input_tokens)}</dd>
            </div>
            {detail.data.cost_micros !== null && (
              <div>
                <dt className="text-muted">{t('conversations.usage.cost')}</dt>
                <dd className="font-medium tabular-nums">{formatMoney(detail.data.cost_micros)}</dd>
              </div>
            )}
          </dl>
          {usage.length === 0 ? (
            <p className="text-sm text-muted">{t('conversations.usage.empty')}</p>
          ) : (
            <ul className="divide-y divide-border text-sm">
              {usage.map((u) => (
                <li key={`${u.kind}/${u.provider}/${u.sku}/${u.unit}`} className="flex flex-wrap items-baseline justify-between gap-2 py-2">
                  <span className="min-w-0">
                    <span className="font-medium">{kindLabel(u.kind)}</span>{' '}
                    <span className="text-muted">
                      {u.sku} · {formatNumber(u.quantity)} {unitLabel(u.unit)}
                    </span>
                    {!u.rated && (
                      <Badge tone="warning" className="ml-2">
                        {t('conversations.usage.unrated')}
                      </Badge>
                    )}
                  </span>
                  {u.cost_micros !== null && <span className="tabular-nums">{formatMoney(u.cost_micros)}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}
