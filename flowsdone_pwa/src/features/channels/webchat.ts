import type { ChannelConnection } from '@/core/admin/types'

/** The web chat's allowed origins as stored in the connection's config. */
export function originsOf(connection: ChannelConnection | null): string[] {
  const value = connection?.config?.allowed_origins
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []
}

/** One origin per line (or comma-separated); the gateway normalizes and validates them. */
export function parseOrigins(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((v) => v.trim())
    .filter(Boolean)
}

/**
 * The code a tenant pastes on their website to show the web chat.
 *
 * @param connection - A webchat connection (with its `webchat` URLs).
 * @returns The HTML snippet, or null if the gateway didn't send the URLs.
 */
export function webchatSnippet(connection: ChannelConnection): string | null {
  const embed = connection.webchat
  if (!embed) return null
  const css = embed.script_url.replace(/\.js$/, '.css')
  return [
    `<link rel="stylesheet" href="${css}" />`,
    '<script>',
    '  window.AgentChatConfig = {',
    `    wsUrl: "${embed.ws_url}",`,
    `    channelKey: "${connection.external_id}"`,
    '  };',
    '</script>',
    `<script src="${embed.script_url}" defer></script>`,
  ].join('\n')
}
