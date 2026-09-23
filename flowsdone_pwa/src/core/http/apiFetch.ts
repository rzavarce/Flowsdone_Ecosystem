/**
 * Shared HTTP client for talking to the gateway (`/api/...`).
 *
 * - Sends the session cookie (`credentials: 'include'`).
 * - Adds `X-Requested-With: fd-console`, which the gateway requires on every
 *   data-changing request sent with a cookie (CSRF defense): a foreign origin
 *   can't send that header without CORS permission.
 * - Translates error responses into {@link ApiError}, using the gateway's
 *   `detail` as the message.
 */

/** Headers the gateway requires to accept cookie-authenticated writes. */
export const CSRF_HEADERS = { 'X-Requested-With': 'fd-console' } as const

/** Error returned by the gateway (or a network error if `status` is 0). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Options for {@link apiFetch}. */
export interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON body. */
  body?: unknown
  /** Injectable `fetch` for tests. */
  fetchFn?: typeof fetch
  /** API base; defaults to `/api`. */
  baseUrl?: string
}

/**
 * Extracts a readable message from a FastAPI error response.
 *
 * @param res - Response with an error status.
 * @returns The `detail` if it's text; a summary if it's the validation list
 *   (422); or a generic message with the status code.
 */
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? ''}`.trim())
        .join('; ')
    }
  } catch {
    // Cuerpo vacío o no JSON: se usa el mensaje genérico.
  }
  return `Error ${res.status}`
}

/**
 * Calls the gateway and returns the typed JSON (or `undefined` on a 204).
 *
 * @param path - Path under the base, with a leading `/` (e.g. `/admin/projects`).
 * @param options - Method, body and injectable dependencies.
 * @returns The response's JSON body.
 * @throws ApiError with the gateway's status and message; `status` 0 if
 *   there was no connection.
 */
export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { method = 'GET', body, fetchFn = (...a) => fetch(...a), baseUrl = '/api' } = options
  let res: Response
  try {
    res = await fetchFn(`${baseUrl}${path}`, {
      method,
      credentials: 'include',
      headers: {
        ...CSRF_HEADERS,
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'No se pudo contactar con el servidor. Inténtalo de nuevo.')
  }
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
