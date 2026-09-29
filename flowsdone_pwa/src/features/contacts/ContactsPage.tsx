import { ArrowLeft, ArrowRight, Contact as ContactIcon } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { Spinner } from '@/components/ui/Spinner'
import { useContact, useContacts, useUpdateContact } from '@/core/admin/billingHooks'
import type { ContactRecord } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { currentLocale } from '@/core/i18n/i18n'
import { useTenant } from '@/core/tenant/useTenant'
import { channelLabel, DEMO_CHANNEL, identifierLabel } from '@/features/billing/labels'
import { CHANNEL_TYPE_LIST } from '@/features/channels/channelTypes'
import { ContactCardView } from '@/features/conversations/ContactCardPanel'
import { cn } from '@/lib/cn'
import { ContactAvatar } from './ContactAvatar'
import { useTranslation } from 'react-i18next'

/** Short date and time in the active language. */
const shortWhen = (iso: string) => new Date(iso).toLocaleString(currentLocale(), { dateStyle: 'short', timeStyle: 'short' })

/** How a contact is shown: the name on their card, else their @user, else their identifier. */
const displayName = (c: ContactRecord) => c.name || c.username || identifierLabel(c.identifier)

/** Props for {@link ContactDetail}. */
interface ContactDetailProps {
  contactId: string
  onBack: () => void
}

/** One contact: their card (editable) and their latest conversations. */
function ContactDetail({ contactId, onBack }: ContactDetailProps) {
  const { t } = useTranslation()
  const detail = useContact(contactId)
  const update = useUpdateContact()

  if (detail.isPending) return <Spinner label={t('contacts.loading')} className="py-20" />
  if (detail.isError) return <Alert tone="danger">{describeError(detail.error)}</Alert>

  const { contact, conversations } = detail.data
  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={onBack} className="lg:hidden">
        <ArrowLeft className="size-4" aria-hidden="true" />
        {t('contacts.back')}
      </Button>

      <Card className="p-5">
        <div className="flex items-center gap-4">
          <ContactAvatar name={contact.name || contact.username} channelType={contact.channel_type} />
          <div className="min-w-0">
            <h2 className="truncate text-xl font-semibold">{displayName(contact)}</h2>
            <p className="mt-0.5 text-sm text-muted">
              {channelLabel(contact.channel_type)} · {t('contacts.conversations', { count: contact.conversation_count })}
            </p>
          </div>
        </div>
      </Card>

      <ContactCardView
        identifier={contact.identifier}
        card={contact}
        onSave={(input) => update.mutateAsync({ id: contact.id, input })}
      />

      <Card>
        <CardHeader
          title={t('contacts.recent')}
          description={t('contacts.recentHint')}
          action={
            contact.conversation_count > conversations.length && (
              <Link
                to={`/conversations?contact=${encodeURIComponent(contact.identifier)}`}
                className="flex shrink-0 items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                {t('contacts.seeAll')}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            )
          }
        />
        <div className="p-3 pt-2 sm:px-4">
          {conversations.length === 0 ? (
            <p className="p-2 text-sm text-muted">{t('contacts.noConversations')}</p>
          ) : (
            <ul aria-label={t('contacts.recent')}>
              {conversations.map((c) => (
                <li key={c.id}>
                  <Link
                    to={`/conversations?c=${encodeURIComponent(c.id)}`}
                    className="flex items-center justify-between gap-3 rounded-xl p-3 text-sm transition hover:bg-surface-muted"
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">{shortWhen(c.started_at)}</span>
                      <span className="block text-xs text-muted">
                        {t('conversations.messages', { count: c.inbound_count + c.outbound_count })}
                      </span>
                    </span>
                    <Badge tone={c.status === 'open' ? 'success' : 'neutral'}>{t(`conversations.status.${c.status}`)}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}

/**
 * Contact list: the people behind the visible tenants' conversations (the
 * top bar's tenant selector scopes it), searchable by name, email, phone,
 * @user or identifier and filterable by channel. Selecting one shows their
 * card and latest conversations next to the list.
 */
export function ContactsPage() {
  const { t } = useTranslation()
  const { current } = useTenant()
  const [channel, setChannel] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search.trim())
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('id')
  const setSelectedId = (id: string | null) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (id) next.set('id', id)
        else next.delete('id')
        return next
      },
      { replace: true },
    )
  const openItem = (id: string) => {
    setSelectedId(id)
    // The detail is at the top of the page: bring it into view (on small
    // screens it replaces the list, which may be scrolled far down).
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const list = useContacts({ tenant_id: current?.id, q: deferredSearch || undefined, channel_type: channel || undefined })
  const items = list.data?.pages.flat() ?? []

  return (
    <>
      <PageHeader title={t('nav.contacts')} description={t('contacts.description')} />

      <div className="grid gap-6 lg:grid-cols-[minmax(20rem,26rem)_1fr]">
        <div className={cn('min-w-0 space-y-4', selectedId && 'hidden lg:block')}>
          <Card className="grid gap-3 p-4" role="search" aria-label={t('contacts.filters.label')}>
            <Input
              type="search"
              aria-label={t('contacts.filters.search')}
              placeholder={t('contacts.filters.searchPlaceholder')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Select aria-label={t('conversations.filters.channel')} value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="">{t('conversations.filters.allChannels')}</option>
              {CHANNEL_TYPE_LIST.map((c) => (
                <option key={c.type} value={c.type}>
                  {c.label}
                </option>
              ))}
              <option value={DEMO_CHANNEL}>{t('conversations.filters.demo')}</option>
            </Select>
          </Card>

          {list.isPending ? (
            <Spinner label={t('contacts.loading')} className="py-16" />
          ) : list.isError ? (
            <Alert tone="danger">
              <p>{t('contacts.loadError', { error: describeError(list.error) })}</p>
              <Button variant="secondary" size="sm" className="mt-3" onClick={() => void list.refetch()}>
                {t('common.retry')}
              </Button>
            </Alert>
          ) : items.length === 0 ? (
            <EmptyState icon={ContactIcon} title={t('contacts.empty.title')} description={t('contacts.empty.description')} />
          ) : (
            <Card>
              <ul className="p-2" aria-label={t('nav.contacts')}>
                {items.map((c) => {
                  const title = displayName(c)
                  // Details not already in the title (a phone shown as the name isn't repeated).
                  const details = [c.phone, c.email, c.username].filter((v): v is string => Boolean(v) && v !== title)
                  const when = c.last_message_at ? ` · ${shortWhen(c.last_message_at)}` : ''
                  return (
                    <li key={c.id}>
                      <button
                        type="button"
                        onClick={() => openItem(c.id)}
                        aria-current={c.id === selectedId ? 'true' : undefined}
                        className={cn(
                          'flex w-full cursor-pointer items-center gap-3 rounded-xl p-3 text-left transition hover:bg-surface-muted',
                          c.id === selectedId && 'bg-surface-muted',
                        )}
                      >
                        <ContactAvatar name={c.name || c.username} channelType={c.channel_type} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{title}</span>
                          {details.length > 0 && <span className="block truncate text-xs text-muted">{details.join(' · ')}</span>}
                          <span className="block truncate text-xs text-muted">
                            {channelLabel(c.channel_type)} · {t('contacts.conversations', { count: c.conversation_count })}
                            {when}
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
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
            <ContactDetail key={selectedId} contactId={selectedId} onBack={() => setSelectedId(null)} />
          ) : (
            <Card className="flex min-h-64 items-center justify-center p-8 text-center text-sm text-muted">
              {t('contacts.selectPrompt')}
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
