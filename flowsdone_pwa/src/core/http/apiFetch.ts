/**
 * Cliente HTTP compartido para hablar con el gateway (`/api/...`).
 *
 * - Envía la cookie de sesión (`credentials: 'include'`).
 * - Añade `X-Requested-With: fd-console`, que el gateway exige en toda
 *   petición que cambia datos y va con cookie (defensa CSRF): un origen ajeno
 *   no puede enviar esa cabecera sin permiso CORS.
 * - Traduce las respuestas de error a {@link ApiError}, con el `detail` del
 *   gateway como mensaje.
 */

/** Cabeceras que el gateway exige para aceptar escrituras con cookie. */
export const CSRF_HEADERS = { 'X-Requested-With': 'fd-console' } as const

/** Error devuelto por el gateway (o de red si `status` es 0). */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Opciones de {@link apiFetch}. */
export interface ApiFetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Cuerpo JSON. */
  body?: unknown
  /** `fetch` inyectable para tests. */
  fetchFn?: typeof fetch
  /** Base de la API; por defecto `/api`. */
  baseUrl?: string
}

/**
 * Extrae un mensaje legible de una respuesta de error de FastAPI.
 *
 * @param res - Respuesta con estado de error.
 * @returns El `detail` si es texto; un resumen si es la lista de validación
 *   (422); o un mensaje genérico con el código.
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
 * Llama al gateway y devuelve el JSON tipado (o `undefined` en un 204).
 *
 * @param path - Ruta bajo la base, con `/` inicial (p. ej. `/admin/projects`).
 * @param options - Método, cuerpo y dependencias inyectables.
 * @returns El cuerpo JSON de la respuesta.
 * @throws ApiError con el estado y el mensaje del gateway; `status` 0 si no
 *   hubo conexión.
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
