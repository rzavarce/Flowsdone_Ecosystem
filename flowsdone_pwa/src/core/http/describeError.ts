import { ApiError } from './apiFetch'

/**
 * Traduce un error del gateway a un mensaje accionable para la persona usuaria.
 *
 * @param error - Lo lanzado por una consulta o mutación.
 * @returns Texto en español; para errores desconocidos, el mensaje original.
 */
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : 'Ocurrió un error inesperado.'
  switch (error.status) {
    case 0:
      return error.message
    case 403:
      return 'Tu perfil no tiene permiso para esta acción.'
    case 404:
      return 'Ese elemento ya no existe o no tienes acceso a él.'
    case 409:
      return 'Ya existe un elemento con esos datos (por ejemplo, este canal ya está conectado).'
    case 502:
      return `La plataforma rechazó el registro del canal: ${error.message.replace(/^webhook registration failed:\s*/i, '')}`
    default:
      return error.message
  }
}
