import type { ChannelType, OverageMode } from '@/core/admin/types'
import { i18n } from '@/core/i18n/i18n'
import { CHANNEL_TYPES } from '@/features/channels/channelTypes'

/**
 * Channel of the conversations opened from a share link (the agents' "Share"
 * button). It is not a channel you can create, so it is not in CHANNEL_TYPES.
 */
export const DEMO_CHANNEL = 'demo'

/** Display name of a channel type; `*` is "any other channel"; unknown types are shown as-is. */
export function channelLabel(type: string): string {
  if (type === '*') return i18n.t('plans.fields.anyChannel')
  if (type === DEMO_CHANNEL) return i18n.t('conversations.filters.demo')
  return CHANNEL_TYPES[type as ChannelType]?.label ?? type
}

/**
 * Readable form of a conversation's channel identifier: calls from the demo
 * page's softphone come as "client:demo-xxxxxxxx", WhatsApp contacts as
 * "34600111222@s.whatsapp.net"; everything else as-is.
 */
export function identifierLabel(contact: string): string {
  const call = /^client:(demo-[a-z0-9]+)$/i.exec(contact)
  if (call) return i18n.t('conversations.browserCall', { id: call[1] })
  const whatsapp = /^(\d+)@s\.whatsapp\.net$/.exec(contact)
  return whatsapp ? `+${whatsapp[1]}` : contact
}

/** How to show a conversation's contact: the name on its card, or its identifier. */
export function contactLabel(conversation: { contact: string; contact_name?: string | null }): string {
  return conversation.contact_name || identifierLabel(conversation.contact)
}

/** Display name of an overage mode. */
export function modeLabel(mode: OverageMode): string {
  return i18n.t(`plans.modes.${mode}.label`)
}

/** Display name of a usage unit ("input_token" -> "tokens de entrada"); unknown units as-is. */
export function unitLabel(unit: string): string {
  const key = `costs.units.${unit}`
  return i18n.exists(key) ? i18n.t(key as 'costs.units.message') : unit
}

/** Display name of a usage kind (channel, llm, platform). */
export function kindLabel(kind: string): string {
  const key = `costs.kinds.${kind}`
  return i18n.exists(key) ? i18n.t(key as 'costs.kinds.llm') : kind
}
