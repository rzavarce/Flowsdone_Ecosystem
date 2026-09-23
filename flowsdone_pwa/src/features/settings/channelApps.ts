import type { ChannelAppProvider } from '@/core/admin/types'

/** A secret value of the shared app (sent inside `credentials`). */
export interface AppCredentialField {
  key: string
  label: string
  hint?: string
  required?: boolean
}

/** What the shared app needs from each provider; checked against the gateway's webhooks. */
export interface ChannelAppConfig {
  provider: ChannelAppProvider
  label: string
  description: string
  fields: AppCredentialField[]
}

/**
 * Platform-wide app credentials, one entry per provider (Meta, X, TikTok,
 * Twilio), shared across all tenants and configured once by an admin from
 * `PlatformIntegrations`.
 */
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
