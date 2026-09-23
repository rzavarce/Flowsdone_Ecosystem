import { AtSign, MessageCircle, MessagesSquare, Music2, PhoneCall, Send, Share2, type LucideIcon } from 'lucide-react'
import type { ChannelType } from '@/core/admin/types'
import { i18n } from '@/core/i18n/i18n'

/** A secret value specific to the connection (sent inside `credentials`). */
export interface CredentialField {
  key: string
  label: string
  hint?: string
  required?: boolean
}

/** What each channel needs to connect; checked against the gateway's webhooks/senders. */
export interface ChannelTypeConfig {
  type: ChannelType
  label: string
  icon: LucideIcon
  /** Name of the channel's unique identifier (`external_id`). */
  externalIdLabel: string
  externalIdHint: string
  externalIdPlaceholder: string
  /** Per-connection credentials (empty if the channel doesn't need any). */
  credentials: CredentialField[]
  /** Note about what the gateway does automatically on save. */
  note?: string
}

/**
 * Per-channel-type configuration: label, icon, what identifies a connection
 * and which credentials it requires. Drives both the connection form's
 * fields and the display copy across the Channels screen.
 */
/** Translates a channel-type text when read (so it follows language changes). */
const tr = (key: string) => i18n.t(`channels.types.${key}` as 'channels.types.telegram.label')

/** Builds a channel type whose texts are getters over `channels.types.<type>.*`. */
function channelType(
  type: ChannelType,
  icon: LucideIcon,
  externalIdPlaceholder: string,
  opts: { credentials?: string[]; note?: boolean; label?: string } = {},
): ChannelTypeConfig {
  return {
    type,
    icon,
    externalIdPlaceholder,
    get label() {
      return opts.label ?? tr(`${type}.label`)
    },
    get externalIdLabel() {
      return tr(`${type}.externalIdLabel`)
    },
    get externalIdHint() {
      return tr(`${type}.externalIdHint`)
    },
    get note() {
      return opts.note ? tr(`${type}.note`) : undefined
    },
    credentials: (opts.credentials ?? []).map((key) => ({
      key,
      required: true,
      get label() {
        return tr(`credentials.${key}.label`)
      },
      get hint() {
        return tr(`credentials.${key}.hint`)
      },
    })),
  }
}

export const CHANNEL_TYPES: Record<ChannelType, ChannelTypeConfig> = {
  whatsapp_evolution: channelType('whatsapp_evolution', MessageCircle, 'clinica-vital', { label: 'WhatsApp' }),
  telegram: channelType('telegram', Send, '123456789:AA…', { label: 'Telegram', note: true }),
  facebook: channelType('facebook', MessagesSquare, '102030405060708', {
    label: 'Facebook Messenger',
    credentials: ['page_access_token'],
    note: true,
  }),
  instagram: channelType('instagram', AtSign, '17841400000000000', {
    label: 'Instagram',
    credentials: ['page_access_token'],
    note: true,
  }),
  twitter: channelType('twitter', Share2, '1234567890', { label: 'X (Twitter)' }),
  tiktok: channelType('tiktok', Music2, 'act.example', { label: 'TikTok' }),
  voice: channelType('voice', PhoneCall, '+34911222333'),
}

/** Types in the order they're offered when creating a channel. */
export const CHANNEL_TYPE_LIST: readonly ChannelTypeConfig[] = Object.values(CHANNEL_TYPES)

/**
 * Masks the sensitive part of a channel's identifier before showing it on screen.
 *
 * Telegram's `external_id` IS the bot token (a secret), and the gateway
 * returns it as-is; the UI should never render it in full.
 *
 * @param type - Channel type.
 * @param externalId - Identifier exactly as returned by the gateway.
 * @returns The identifier, with the Telegram token masked (even if it doesn't
 *   follow the `<id>:<secret>` format, so this doesn't depend on the data being ideal).
 */
export function maskExternalId(type: ChannelType, externalId: string): string {
  if (type !== 'telegram') return externalId
  const colon = externalId.indexOf(':')
  // Formato real de BotFather (`<id numérico>:<secreto>`): el id del bot es público, el resto no.
  if (colon > 0) return `${externalId.slice(0, colon)}:••••••••`
  // Formato inesperado: no se asume nada; solo se deja un prefijo para reconocerlo.
  return `${externalId.slice(0, 4)}••••••••`
}
