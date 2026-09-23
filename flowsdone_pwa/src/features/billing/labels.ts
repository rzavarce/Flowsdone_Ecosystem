import type { ChannelType, OverageMode } from '@/core/admin/types'
import { i18n } from '@/core/i18n/i18n'
import { CHANNEL_TYPES } from '@/features/channels/channelTypes'

/** Display name of a channel type; `*` is "any other channel"; unknown types are shown as-is. */
export function channelLabel(type: string): string {
  if (type === '*') return i18n.t('plans.fields.anyChannel')
  return CHANNEL_TYPES[type as ChannelType]?.label ?? type
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
