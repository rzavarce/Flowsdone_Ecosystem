import { ApiError } from '@/core/http/apiFetch'

/**
 * Retry policy for queries.
 *
 * @param failureCount - Failed attempts so far.
 * @param error - The error from the last attempt.
 * @returns `false` for client errors (4xx: they won't fix themselves); `true`
 *   for network or 5xx errors, up to 2 retries.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 2
}
