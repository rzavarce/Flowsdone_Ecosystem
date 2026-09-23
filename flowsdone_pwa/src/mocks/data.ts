/**
 * Sample data for the mockup. Gets replaced with gateway calls once the API
 * is wired up; the interfaces are the shape the views expect.
 */
import type { BadgeTone } from '@/components/ui/Badge'

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

/** Stat tiles shown on the dashboard. */
export const STATS: readonly Stat[] = [
  { id: 'conversations', label: 'Conversaciones hoy', value: '1.284', delta: 12.4 },
  { id: 'messages', label: 'Mensajes procesados', value: '18.902', delta: 8.1 },
  { id: 'response', label: 'Tiempo de respuesta', value: '1,8 s', delta: -14.2 },
  { id: 'resolution', label: 'Resueltas por IA', value: '87 %', delta: 3.5 },
]

/** Weekly activity series for the dashboard chart. */
export const ACTIVITY: readonly ActivityPoint[] = [
  { label: 'Lun', value: 820 },
  { label: 'Mar', value: 940 },
  { label: 'Mié', value: 880 },
  { label: 'Jue', value: 1120 },
  { label: 'Vie', value: 1290 },
  { label: 'Sáb', value: 760 },
  { label: 'Dom', value: 1284 },
]

/** Most recent conversations shown on the dashboard. */
export const RECENT_CONVERSATIONS: readonly ConversationSummary[] = [
  { id: 'c1', contact: 'Valentina Rojas', channel: 'WhatsApp', preview: '¿Pueden confirmarme la hora de la cita?', time: 'hace 2 min', status: { label: 'IA', tone: 'primary' } },
  { id: 'c2', contact: 'Carlos Méndez', channel: 'Webchat', preview: 'Necesito cambiar el plan contratado.', time: 'hace 9 min', status: { label: 'Escalada', tone: 'warning' } },
  { id: 'c3', contact: 'Lucía Fernández', channel: 'Instagram', preview: 'Gracias, ya quedó resuelto 🙌', time: 'hace 24 min', status: { label: 'Resuelta', tone: 'success' } },
  { id: 'c4', contact: 'Andrés Salcedo', channel: 'Telegram', preview: '¿Tienen facturación electrónica?', time: 'hace 41 min', status: { label: 'IA', tone: 'primary' } },
  { id: 'c5', contact: 'Marta Quintero', channel: 'WhatsApp', preview: 'No me llegó el código de acceso.', time: 'hace 1 h', status: { label: 'Escalada', tone: 'warning' } },
]
