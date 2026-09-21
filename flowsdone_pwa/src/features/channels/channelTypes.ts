import { AtSign, MessageCircle, MessagesSquare, Music2, PhoneCall, Send, Share2, type LucideIcon } from 'lucide-react'
import type { ChannelType } from '@/core/admin/types'

/** Un dato secreto propio de la conexión (se envía en `credentials`). */
export interface CredentialField {
  key: string
  label: string
  hint?: string
  required?: boolean
}

/** Qué necesita cada canal para conectarse; verificado contra los webhooks/senders del gateway. */
export interface ChannelTypeConfig {
  type: ChannelType
  label: string
  icon: LucideIcon
  /** Nombre del identificador único del canal (`external_id`). */
  externalIdLabel: string
  externalIdHint: string
  externalIdPlaceholder: string
  /** Credenciales por conexión (vacío si el canal no necesita ninguna). */
  credentials: CredentialField[]
  /** Nota sobre lo que el gateway hace automáticamente al guardar. */
  note?: string
}

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

/** Tipos en el orden en que se ofrecen al crear un canal. */
export const CHANNEL_TYPE_LIST: readonly ChannelTypeConfig[] = Object.values(CHANNEL_TYPES)

/**
 * Oculta lo sensible del identificador de un canal para mostrarlo en pantalla.
 *
 * El `external_id` de Telegram ES el token del bot (un secreto), y el gateway
 * lo devuelve tal cual; la UI nunca debería pintarlo completo.
 *
 * @param type - Tipo de canal.
 * @param externalId - Identificador tal como lo devuelve el gateway.
 * @returns El identificador, con el token de Telegram enmascarado (también si no
 *   sigue el formato `<id>:<secreto>`, para no depender de que los datos sean ideales).
 */
export function maskExternalId(type: ChannelType, externalId: string): string {
  if (type !== 'telegram') return externalId
  const colon = externalId.indexOf(':')
  // Formato real de BotFather (`<id numérico>:<secreto>`): el id del bot es público, el resto no.
  if (colon > 0) return `${externalId.slice(0, colon)}:••••••••`
  // Formato inesperado: no se asume nada; solo se deja un prefijo para reconocerlo.
  return `${externalId.slice(0, 4)}••••••••`
}

/**
 * Convierte un nombre en un slug (minúsculas, sin acentos, con guiones).
 *
 * @example slugify('Atención al paciente') // 'atencion-al-paciente'
 */
export function slugify(name: string): string {
  return name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
