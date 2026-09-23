import { AtSign, MessageCircle, MessagesSquare, Music2, PhoneCall, Send, Share2, type LucideIcon } from 'lucide-react'
import type { ChannelType } from '@/core/admin/types'

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
export const CHANNEL_TYPES: Record<ChannelType, ChannelTypeConfig> = {
  whatsapp_evolution: {
    type: 'whatsapp_evolution',
    label: 'WhatsApp',
    icon: MessageCircle,
    externalIdLabel: 'Nombre de la instancia',
    externalIdHint: 'La instancia creada en Evolution API.',
    externalIdPlaceholder: 'clinica-vital',
    credentials: [],
  },
  telegram: {
    type: 'telegram',
    label: 'Telegram',
    icon: Send,
    externalIdLabel: 'Token del bot',
    externalIdHint: 'Te lo entrega @BotFather al crear el bot.',
    externalIdPlaceholder: '123456789:AA…',
    credentials: [],
    note: 'Al guardar, Flowsdone registra el webhook del bot en Telegram automáticamente.',
  },
  facebook: {
    type: 'facebook',
    label: 'Facebook Messenger',
    icon: MessagesSquare,
    externalIdLabel: 'ID de la página',
    externalIdHint: 'El ID numérico de la página de Facebook.',
    externalIdPlaceholder: '102030405060708',
    credentials: [
      { key: 'page_access_token', label: 'Token de acceso de la página', hint: 'De la app de Meta, con permiso de mensajería.', required: true },
    ],
    note: 'Al guardar, Flowsdone suscribe la página a la app de Meta automáticamente.',
  },
  instagram: {
    type: 'instagram',
    label: 'Instagram',
    icon: AtSign,
    externalIdLabel: 'ID de la cuenta de Instagram Business',
    externalIdHint: 'El ID de la cuenta profesional vinculada a la página.',
    externalIdPlaceholder: '17841400000000000',
    credentials: [
      { key: 'page_access_token', label: 'Token de acceso de la página', hint: 'De la app de Meta, con permiso de mensajería.', required: true },
    ],
    note: 'Al guardar, Flowsdone suscribe la cuenta a la app de Meta automáticamente.',
  },
  twitter: {
    type: 'twitter',
    label: 'X (Twitter)',
    icon: Share2,
    externalIdLabel: 'ID de usuario de X',
    externalIdHint: 'El ID numérico de la cuenta (for_user_id).',
    externalIdPlaceholder: '1234567890',
    credentials: [],
  },
  tiktok: {
    type: 'tiktok',
    label: 'TikTok',
    icon: Music2,
    externalIdLabel: 'open_id de TikTok',
    externalIdHint: 'El identificador de la cuenta en TikTok.',
    externalIdPlaceholder: 'act.example',
    credentials: [],
  },
  voice: {
    type: 'voice',
    label: 'Voz (teléfono)',
    icon: PhoneCall,
    externalIdLabel: 'Número de teléfono',
    externalIdHint: 'En formato internacional (E.164).',
    externalIdPlaceholder: '+34911222333',
    credentials: [],
  },
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
