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
      return 'Ya existe un elemento con esos datos (por ejemplo, ese email o ese identificador ya están en uso).'
    case 502:
      // Se guardó del lado del gateway pero un paso externo falló (registro de
      // webhook de un canal, o el email de activación de un usuario/tenant) -
      // se despoja el prefijo técnico en inglés del detail y se deja el motivo.
      return `Se guardó, pero un paso externo falló: ${error.message.replace(
        /^(webhook registration failed|user created but the activation email could not be sent|tenant created but the client's activation email could not be sent):\s*/i,
        '',
      )}`
    default:
      return error.message
  }
}
