import { MonitorSmartphone } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'
import type { ChannelType } from '@/core/admin/types'
import { CHANNEL_TYPES } from '@/features/channels/channelTypes'

/** Props for {@link ContactAvatar}. */
export interface ContactAvatarProps {
  /** The name on the contact's card, if it has a real one. */
  name?: string | null
  channelType: string
}

/** A name worth initials: has a letter and isn't a generic "client:…" identity. */
const isRealName = (name?: string | null): name is string =>
  Boolean(name && /\p{L}/u.test(name) && !name.startsWith('client:'))

/**
 * A contact's avatar: their initials when they have a name, else their
 * channel's icon (initials of "+34 600…" or "client:demo-…" say nothing).
 */
export function ContactAvatar({ name, channelType }: ContactAvatarProps) {
  if (isRealName(name)) return <Avatar name={name.replace(/^@/, '')} />
  const Icon = CHANNEL_TYPES[channelType as ChannelType]?.icon ?? MonitorSmartphone
  return (
    <span
      aria-hidden="true"
      className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-muted text-muted"
    >
      <Icon className="size-4" />
    </span>
  )
}
