import { MessageSquare } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useConversations } from '@/core/admin/billingHooks'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { useTenant } from '@/core/tenant/useTenant'
import { channelLabel } from '@/features/billing/labels'
import { CHANNEL_TYPE_LIST } from '@/features/channels/channelTypes'
import { cn } from '@/lib/cn'
import { ConversationDetail } from './ConversationDetail'
import { useTranslation } from 'react-i18next'

type StatusFilter = '' | 'open' | 'closed'

/**
 * Conversation inbox: the visible tenants' conversations (the top bar's
 * tenant selector scopes it), filterable by status, channel and contact,
 * with "load more" pagination. Selecting one shows its transcript and usage
 * next to the list (or instead of it, on small screens).
 */
export function ConversationsPage() {
  const { t } = useTranslation()
  const { current } = useTenant()
  const [status, setStatus] = useState<StatusFilter>('')
  const [channel, setChannel] = useState('')
  const [contact, setContact] = useState('')
  const deferredContact = useDeferredValue(contact.trim())
  // The open conversation lives in the URL (`?c=`), so the global search
  // and shared links can open one directly.
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('c')
  const setSelectedId = (id: string | null) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (id) next.set('c', id)
        else next.delete('c')
        return next
      },
      { replace: true },
    )

  const list = useConversations({
    tenant_id: current?.id,
    status: status || undefined,
    channel_type: channel || undefined,
    contact: deferredContact || undefined,
  })
  const items = list.data?.pages.flat() ?? []

  return (
    <>
      <PageHeader title={t('nav.conversations')} description={t('conversations.description')} />

      <div className="grid gap-6 lg:grid-cols-[minmax(20rem,26rem)_1fr]">
        <div className={cn('min-w-0 space-y-4', selectedId && 'hidden lg:block')}>
          <Card className="grid grid-cols-2 gap-3 p-4" role="search" aria-label={t('conversations.filters.label')}>
            <Select
              aria-label={t('conversations.filters.status')}
              value={status}
              onChange={(e) => setStatus(e.target.value as StatusFilter)}
            >
              <option value="">{t('conversations.filters.all')}</option>
              <option value="open">{t('conversations.status.open')}</option>
              <option value="closed">{t('conversations.status.closed')}</option>
            </Select>
            <Select aria-label={t('conversations.filters.channel')} value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="">{t('conversations.filters.allChannels')}</option>
              {CHANNEL_TYPE_LIST.map((c) => (
                <option key={c.type} value={c.type}>
                  {c.label}
                </option>
              ))}
            </Select>
            <Input
              className="col-span-2"
              type="search"
              aria-label={t('conversations.filters.contact')}
              placeholder={t('conversations.filters.contactPlaceholder')}
              value={contact}
              onChange={(e) => setContact(e.target.value)}
            />
          </Card>

          {list.isPending ? (
            <Spinner label={t('conversations.loading')} className="py-16" />
          ) : list.isError ? (
            <Alert tone="danger">
              <p>{t('conversations.loadError', { error: describeError(list.error) })}</p>
              <Button variant="secondary" size="sm" className="mt-3" onClick={() => void list.refetch()}>
                {t('common.retry')}
              </Button>
            </Alert>
          ) : items.length === 0 ? (
            <EmptyState icon={MessageSquare} title={t('conversations.empty.title')} description={t('conversations.empty.description')} />
          ) : (
            <Card>
              <ul className="p-2" aria-label={t('nav.conversations')}>
                {items.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(c.id)}
                      aria-current={c.id === selectedId ? 'true' : undefined}
                      className={cn(
                        'flex w-full cursor-pointer items-center gap-3 rounded-xl p-3 text-left transition hover:bg-surface-muted',
                        c.id === selectedId && 'bg-surface-muted',
                      )}
                    >
                      <Avatar name={c.contact} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{c.contact}</span>
                        <span className="block truncate text-xs text-muted">
                          {channelLabel(c.channel_type)} · {t('conversations.messages', { count: c.inbound_count + c.outbound_count })}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end gap-1">
                        <Badge tone={c.status === 'open' ? 'success' : 'neutral'}>{t(`conversations.status.${c.status}`)}</Badge>
                        <span className="text-xs text-muted">
                          {new Date(c.last_message_at).toLocaleString(currentLocale(), { dateStyle: 'short', timeStyle: 'short' })}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {list.hasNextPage && (
                <div className="p-3 pt-0">
                  <Button variant="secondary" className="w-full" onClick={() => void list.fetchNextPage()} disabled={list.isFetchingNextPage}>
                    {t('conversations.loadMore')}
                  </Button>
                </div>
              )}
            </Card>
          )}
        </div>

        <div className={cn('min-w-0', !selectedId && 'hidden lg:block')}>
          {selectedId ? (
            <ConversationDetail conversationId={selectedId} onBack={() => setSelectedId(null)} />
          ) : (
            <Card className="flex min-h-64 items-center justify-center p-8 text-center text-sm text-muted">
              {t('conversations.selectPrompt')}
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
