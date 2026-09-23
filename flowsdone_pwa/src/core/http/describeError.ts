import { i18n } from '@/core/i18n/i18n'
import { ApiError } from './apiFetch'

/**
 * Translates a gateway error into an actionable message for the user.
 *
 * @param error - Whatever a query or mutation threw.
 * @returns Copy in the active language; for unknown errors, the original message.
 */
export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) return error instanceof Error ? error.message : i18n.t('common.unexpectedError')
  switch (error.status) {
    case 0:
      return error.message
    case 403:
      return i18n.t('errors.forbidden')
    case 404:
      return i18n.t('errors.notFound')
    case 409:
      return i18n.t('errors.conflict')
    case 502:
      // Se guardó del lado del gateway pero un paso externo falló (registro de
      // webhook de un canal, o el email de activación de un usuario/tenant) -
      // se despoja el prefijo técnico en inglés del detail y se deja el motivo.
      return i18n.t('errors.partial', {
        reason: error.message.replace(
        /^(webhook registration failed|user created but the activation email could not be sent|tenant created but the client's activation email could not be sent):\s*/i,
          '',
        ),
      })
    default:
      return error.message
  }
}
