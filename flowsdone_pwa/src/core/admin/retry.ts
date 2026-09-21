import { ApiError } from '@/core/http/apiFetch'

/**
 * Política de reintentos de las consultas.
 *
 * @param failureCount - Intentos fallidos hasta ahora.
 * @param error - El error del último intento.
 * @returns `false` para errores del cliente (4xx: no se arreglan solos); `true`
 *   para los de red o 5xx, hasta 2 reintentos.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}
