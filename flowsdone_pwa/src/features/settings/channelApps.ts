import type { ChannelAppProvider } from '@/core/admin/types'
import { i18n } from '@/core/i18n/i18n'

/** A value of the shared app: a secret (sent inside `credentials`) or, with `config`, a plain setting (sent inside `config`). */
export interface AppCredentialField {
  key: string
  label: string
  hint?: string
  required?: boolean
  /** Not a secret: goes in the app's `config` and is typed in clear text. */
  config?: boolean
  /** Sent as a number (e.g. Chatwoot's account id). */
  numeric?: boolean
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
 * Twilio, Chatwoot), shared across all tenants and configured once by an admin from
 * `PlatformIntegrations`.
 */
/** Translates a platform-app text when read (follows language changes). */
const tr = (key: string) => i18n.t(`settings.apps.${key}` as 'settings.apps.meta.description')

/** A credential field whose label is the raw key name (a brand term) and whose hint is translated. */
const field = (
  provider: ChannelAppProvider,
  key: string,
  label: string,
  opts: { hint?: boolean; required?: boolean; config?: boolean; numeric?: boolean } = {},
): AppCredentialField => ({
  key,
  required: opts.required,
  config: opts.config,
  numeric: opts.numeric,
  get label() {
    return key === 'webhook_verify_token' ? tr(`${provider}.fields.${key}.label`) : label
  },
  get hint() {
    return opts.hint ? tr(`${provider}.fields.${key}.hint`) : undefined
  },
})

/** An app whose label and description are getters. */
const app = (provider: ChannelAppProvider, fields: AppCredentialField[], translatedLabel = false, label = ''): ChannelAppConfig => ({
  provider,
  fields,
  get label() {
    return translatedLabel ? tr(`${provider}.label`) : label
  },
  get description() {
    return tr(`${provider}.description`)
  },
})

export const CHANNEL_APPS: readonly ChannelAppConfig[] = [
  app('meta', [
    field('meta', 'app_secret', 'App Secret', { hint: true, required: true }),
    field('meta', 'webhook_verify_token', '', { hint: true }),
  ], false, 'Meta (Facebook + Instagram)'),
  app('twitter', [field('twitter', 'consumer_secret', 'Consumer Secret', { required: true })], false, 'X (Twitter)'),
  app('tiktok', [field('tiktok', 'client_secret', 'Client Secret', { required: true })], false, 'TikTok'),
  app('twilio', [
    field('twilio', 'auth_token', 'Auth Token', { hint: true, required: true }),
    field('twilio', 'account_sid', 'Account SID', { hint: true }),
  ], true),
  app('chatwoot', [
    field('chatwoot', 'api_access_token', 'Access Token', { hint: true, required: true }),
    field('chatwoot', 'account_id', 'Account ID', { hint: true, required: true, config: true, numeric: true }),
    field('chatwoot', 'base_url', 'Base URL', { hint: true, config: true }),
  ], false, 'Chatwoot (Facebook + Instagram)'),
]
