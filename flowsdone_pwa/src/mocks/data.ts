/**
 * Datos de ejemplo de la maqueta. Se reemplazan por llamadas al gateway
 * cuando se conecte la API; las interfaces son la forma que esperan las vistas.
 */
import type { BadgeTone } from '@/components/ui/Badge'

export interface Stat {
  id: string
  label: string
  value: string
  /** Variación respecto al periodo anterior, en %. */
  delta: number
}

export interface ActivityPoint {
  label: string
  value: number
}

export interface ConversationSummary {
  id: string
  contact: string
  channel: string
  preview: string
  time: string
  status: { label: string; tone: BadgeTone }
}

export interface ChannelSummary {
  id: string
  name: string
  description: string
  status: { label: string; tone: BadgeTone }
  messages: number
}

export const STATS: readonly Stat[] = [
  { id: 'conversations', label: 'Conversaciones hoy', value: '1.284', delta: 12.4 },
  { id: 'messages', label: 'Mensajes procesados', value: '18.902', delta: 8.1 },
  { id: 'response', label: 'Tiempo de respuesta', value: '1,8 s', delta: -14.2 },
  { id: 'resolution', label: 'Resueltas por IA', value: '87 %', delta: 3.5 },
]

export const ACTIVITY: readonly ActivityPoint[] = [
  { label: 'Lun', value: 820 },
  { label: 'Mar', value: 940 },
  { label: 'Mié', value: 880 },
  { label: 'Jue', value: 1120 },
  { label: 'Vie', value: 1290 },
  { label: 'Sáb', value: 760 },
  { label: 'Dom', value: 1284 },
]

export const RECENT_CONVERSATIONS: readonly ConversationSummary[] = [
  { id: 'c1', contact: 'Valentina Rojas', channel: 'WhatsApp', preview: '¿Pueden confirmarme la hora de la cita?', time: 'hace 2 min', status: { label: 'IA', tone: 'primary' } },
  { id: 'c2', contact: 'Carlos Méndez', channel: 'Webchat', preview: 'Necesito cambiar el plan contratado.', time: 'hace 9 min', status: { label: 'Escalada', tone: 'warning' } },
  { id: 'c3', contact: 'Lucía Fernández', channel: 'Instagram', preview: 'Gracias, ya quedó resuelto 🙌', time: 'hace 24 min', status: { label: 'Resuelta', tone: 'success' } },
  { id: 'c4', contact: 'Andrés Salcedo', channel: 'Telegram', preview: '¿Tienen facturación electrónica?', time: 'hace 41 min', status: { label: 'IA', tone: 'primary' } },
  { id: 'c5', contact: 'Marta Quintero', channel: 'WhatsApp', preview: 'No me llegó el código de acceso.', time: 'hace 1 h', status: { label: 'Escalada', tone: 'warning' } },
]

export const CHANNELS: readonly ChannelSummary[] = [
  { id: 'whatsapp', name: 'WhatsApp', description: 'Evolution API', status: { label: 'Conectado', tone: 'success' }, messages: 9420 },
  { id: 'webchat', name: 'Webchat', description: 'Widget propio (WebSocket)', status: { label: 'Conectado', tone: 'success' }, messages: 5210 },
  { id: 'instagram', name: 'Instagram', description: 'Meta Graph API', status: { label: 'Conectado', tone: 'success' }, messages: 2318 },
  { id: 'telegram', name: 'Telegram', description: 'Bot API', status: { label: 'Conectado', tone: 'success' }, messages: 1204 },
  { id: 'voice', name: 'Voz', description: 'Softphone / transcripción', status: { label: 'Pendiente', tone: 'warning' }, messages: 0 },
  { id: 'facebook', name: 'Facebook', description: 'Messenger', status: { label: 'Desconectado', tone: 'danger' }, messages: 0 },
]
