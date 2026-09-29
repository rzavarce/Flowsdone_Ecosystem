import { Pencil } from 'lucide-react'
import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { Card, CardHeader } from '@/components/ui/Card'
import { Dialog } from '@/components/ui/Dialog'
import { Field } from '@/components/ui/Field'
import { Input } from '@/components/ui/Input'
import { useUpdateConversationContact } from '@/core/admin/billingHooks'
import type { ContactCard, ContactCardInput, Conversation } from '@/core/admin/types'
import { describeError } from '@/core/http/describeError'
import { identifierLabel } from '@/features/billing/labels'
import { useTranslation } from 'react-i18next'

const FORM_ID = 'contact-card-form'
const FIELDS = ['name', 'email', 'phone', 'username', 'notes'] as const

/** Props for {@link ContactCardDialog}. */
export interface ContactCardDialogProps {
  /** The channel identifier the card belongs to (shown in the description). */
  identifier: string
  card: ContactCard | null
  /** Saves the changed fields; rejecting keeps the dialog open with the error. */
  onSave: (input: ContactCardInput) => Promise<unknown>
  onClose: () => void
}

/**
 * Edits the card of a conversation's contact. Only changed fields are sent;
 * emptying one clears it. The card is shared by every conversation with the
 * same identifier on the same channel; the gateway starts it with what the
 * channel and the chat tell, and what staff type here always wins.
 */
export function ContactCardDialog({ identifier, card, onSave, onClose }: ContactCardDialogProps) {
  const { t } = useTranslation()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const initial = Object.fromEntries(FIELDS.map((f) => [f, card?.[f] ?? ''])) as Record<(typeof FIELDS)[number], string>
  const [fields, setFields] = useState(initial)

  const set = (key: (typeof FIELDS)[number]) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setFields((f) => ({ ...f, [key]: e.target.value }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const changed = Object.fromEntries(FIELDS.filter((f) => fields[f].trim() !== initial[f].trim()).map((f) => [f, fields[f]]))
    if (Object.keys(changed).length === 0) return onClose()
    setPending(true)
    setError(null)
    try {
      await onSave(changed)
      onClose()
    } catch (err) {
      setError(err)
      setPending(false)
    }
  }

  return (
    <Dialog
      open
      onClose={pending ? () => {} : onClose}
      title={t('conversations.contactCard.edit')}
      description={t('conversations.contactCard.description', { identifier: identifierLabel(identifier) })}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" form={FORM_ID} disabled={pending}>
            {pending ? t('common.saving') : t('common.save')}
          </Button>
        </>
      }
    >
      <form id={FORM_ID} onSubmit={submit} noValidate className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('conversations.contactCard.fields.name')}>
            <Input value={fields.name} onChange={set('name')} maxLength={120} autoComplete="off" />
          </Field>
          <Field label={t('conversations.contactCard.fields.username')}>
            <Input value={fields.username} onChange={set('username')} maxLength={120} autoComplete="off" placeholder="@" />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t('conversations.contactCard.fields.email')}>
            <Input type="email" value={fields.email} onChange={set('email')} maxLength={254} autoComplete="off" />
          </Field>
          <Field label={t('conversations.contactCard.fields.phone')}>
            <Input type="tel" value={fields.phone} onChange={set('phone')} maxLength={40} autoComplete="off" />
          </Field>
        </div>
        <Field label={t('conversations.contactCard.fields.notes')} hint={t('conversations.contactCard.notesHint')}>
          <textarea
            value={fields.notes}
            rows={3}
            maxLength={2000}
            onChange={set('notes')}
            className="w-full rounded-lg border border-input bg-transparent px-4 py-3 text-sm shadow-theme-xs placeholder:text-muted/70 focus-visible:border-primary/60 focus-visible:ring-3 focus-visible:ring-primary/15 focus-visible:outline-none"
          />
        </Field>
        {error !== null && <Alert tone="danger">{describeError(error)}</Alert>}
      </form>
    </Dialog>
  )
}

/** Props for {@link ContactCardView}. */
export interface ContactCardViewProps {
  identifier: string
  card: ContactCard | null
  onSave: (input: ContactCardInput) => Promise<unknown>
}

/** A contact's card with a button to edit it (used by conversations and contacts). */
export function ContactCardView({ identifier, card, onSave }: ContactCardViewProps) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const details = FIELDS.filter((f) => card?.[f])

  return (
    <Card>
      <CardHeader
        title={t('conversations.contactCard.title')}
        action={
          <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
            <Pencil className="size-4" aria-hidden="true" />
            {details.length ? t('conversations.contactCard.edit') : t('conversations.contactCard.add')}
          </Button>
        }
      />
      <div className="p-5 pt-4 sm:px-6">
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          {details.map((f) => (
            <div key={f} className={f === 'notes' ? 'sm:col-span-2' : undefined}>
              <dt className="text-muted">{t(`conversations.contactCard.fields.${f}`)}</dt>
              <dd className="font-medium break-words whitespace-pre-wrap">{card?.[f]}</dd>
            </div>
          ))}
          <div className={details.length % 2 ? undefined : 'sm:col-span-2'}>
            <dt className="text-muted">{t('conversations.contactCard.identifier')}</dt>
            <dd className="font-medium break-all">{identifier}</dd>
          </div>
        </dl>
        {details.length === 0 && <p className="mt-3 text-sm text-muted">{t('conversations.contactCard.empty')}</p>}
      </div>
      {editing && <ContactCardDialog identifier={identifier} card={card} onSave={onSave} onClose={() => setEditing(false)} />}
    </Card>
  )
}

/** Props for {@link ContactCardPanel}. */
export interface ContactCardPanelProps {
  conversation: Conversation
  card: ContactCard | null
}

/** The contact's card next to a conversation. */
export function ContactCardPanel({ conversation, card }: ContactCardPanelProps) {
  const update = useUpdateConversationContact()
  return (
    <ContactCardView
      identifier={conversation.contact}
      card={card}
      onSave={(input) => update.mutateAsync({ id: conversation.id, input })}
    />
  )
}
