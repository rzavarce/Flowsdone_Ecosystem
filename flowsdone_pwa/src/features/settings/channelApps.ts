import type { ChannelAppProvider } from '@/core/admin/types'

/** Un dato secreto de la app compartida (se envía en `credentials`). */
export interface AppCredentialField {
  key: string
  label: string
  hint?: string
  required?: boolean
}

/** Qué necesita la app compartida de cada proveedor; verificado contra los webhooks del gateway. */
export interface ChannelAppConfig {
  provider: ChannelAppProvider
  label: string
  description: string
  fields: AppCredentialField[]
}

export const CHANNEL_APPS: readonly ChannelAppConfig[] = [
  {
    provider: 'meta',
    label: 'Meta (Facebook + Instagram)',
    description: 'Una sola app de Meta para Messenger e Instagram de todos los tenants.',
    fields: [
      { key: 'app_secret', label: 'App Secret', hint: 'Está en el panel de tu app de Meta. Firma todos los webhooks.', required: true },
      {
        key: 'webhook_verify_token',
        label: 'Token de verificación del webhook',
        hint: 'Opcional: si lo dejas vacío, Flowsdone genera uno (y podrás verlo después para pegarlo en Meta).',
      },
    ],
  },
  {
    provider: 'twitter',
    label: 'X (Twitter)',
    description: 'La app de X compartida para todos los tenants.',
    fields: [{ key: 'consumer_secret', label: 'Consumer Secret', required: true }],
  },
  {
    provider: 'tiktok',
    label: 'TikTok',
    description: 'La app de TikTok compartida para todos los tenants.',
    fields: [{ key: 'client_secret', label: 'Client Secret', required: true }],
  },
  {
    provider: 'twilio',
    label: 'Twilio (voz)',
    description: 'La cuenta de Twilio de la plataforma; cada número se conecta como un canal de voz.',
    fields: [
      { key: 'auth_token', label: 'Auth Token', hint: 'Valida que las llamadas entrantes vengan de Twilio.', required: true },
      { key: 'account_sid', label: 'Account SID', hint: 'Opcional.' },
    ],
  },
]
