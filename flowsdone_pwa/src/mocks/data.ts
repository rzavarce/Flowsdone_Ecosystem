/**
 * Sample data for the mockup. Gets replaced with gateway calls once the API
 * is wired up; the interfaces are the shape the views expect.
 */
import type { BadgeTone } from '@/components/ui/Badge'
import { i18n } from '@/core/i18n/i18n'

/** A single dashboard stat tile (value + trend). */
export interface Stat {
  id: string
  label: string
  value: string
  /** Change from the previous period, in %. */
  delta: number
}

/** One point on the activity chart. */
export interface ActivityPoint {
  label: string
  value: number
}

/** Row shown in the recent-conversations list. */
export interface ConversationSummary {
  id: string
  contact: string
  channel: string
  preview: string
  time: string
  status: { label: string; tone: BadgeTone }
}

/** Translates a dashboard sample text when read (follows language changes). */
const tr = (key: string, options?: Record<string, unknown>) => i18n.t(`dashboard.${key}` as 'dashboard.vsLastWeek', options)

/** A stat tile whose label is a getter over `dashboard.stats.<id>`. */
const stat = (id: string, value: string, delta: number): Stat => ({
  id,
  value,
  delta,
  get label() {
    return tr(`stats.${id}`)
  },
})

/** Stat tiles shown on the dashboard. */
export const STATS: readonly Stat[] = [
  stat('conversations', '1.284', 12.4),
  stat('messages', '18.902', 8.1),
  stat('response', '1,8 s', -14.2),
  stat('resolution', '87 %', 3.5),
]

/** Weekly activity series for the dashboard chart (short day names are getters). */
export const ACTIVITY: readonly ActivityPoint[] = (
  [
    ['mon', 820],
    ['tue', 940],
    ['wed', 880],
    ['thu', 1120],
    ['fri', 1290],
    ['sat', 760],
    ['sun', 1284],
  ] as const
).map(([day, value]) => ({
  value,
  get label() {
    return tr(`days.${day}`)
  },
}))

/** Sample conversation; `minutes` and the status become translated getters. */
const conversation = (
  id: string,
  contact: string,
  channel: string,
  preview: string,
  minutes: number,
  status: 'ai' | 'escalated' | 'resolved',
): ConversationSummary => ({
  id,
  contact,
  channel,
  preview,
  get time() {
    return minutes < 60 ? tr('minutesAgo', { count: minutes }) : tr('hoursAgo', { count: Math.round(minutes / 60) })
  },
  status: {
    tone: ({ ai: 'primary', escalated: 'warning', resolved: 'success' } as const)[status],
    get label() {
      return tr(`status.${status}`)
    },
  },
})

/** Most recent conversations shown on the dashboard (message previews are sample content). */
export const RECENT_CONVERSATIONS: readonly ConversationSummary[] = [
  conversation('c1', 'Valentina Rojas', 'WhatsApp', '¿Pueden confirmarme la hora de la cita?', 2, 'ai'),
  conversation('c2', 'Carlos Méndez', 'Webchat', 'Necesito cambiar el plan contratado.', 9, 'escalated'),
  conversation('c3', 'Lucía Fernández', 'Instagram', 'Gracias, ya quedó resuelto 🙌', 24, 'resolved'),
  conversation('c4', 'Andrés Salcedo', 'Telegram', '¿Tienen facturación electrónica?', 41, 'ai'),
  conversation('c5', 'Marta Quintero', 'WhatsApp', 'No me llegó el código de acceso.', 60, 'escalated'),
]
