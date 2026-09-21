/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** `mock` | `http`. Ver core/auth/createAuthApi.ts. */
  readonly VITE_AUTH_MODE?: string
  /** Base de la API del gateway (default `/api`). */
  readonly VITE_API_BASE_URL?: string
  /** URL de Langflow a embeber en /agentes. */
  readonly VITE_LANGFLOW_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
